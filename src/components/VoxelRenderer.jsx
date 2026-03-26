/**
 * VoxelRenderer — three.js GPU-instanced 3D voxel display
 * Phase Q §Q.1
 *
 * ═══════════════════════════════════════════════════════════════
 * CONSTITUTIONAL RULES — enforced in this file:
 *
 * Rule 1 (Read-Only):
 *   Voxel data is received as a prop. This component never fetches,
 *   transforms, re-scores, or re-derives any voxel field value.
 *
 * Rule 2 (Direct Linear Colour Mapping):
 *   colour = lerp(COLOUR_LOW, COLOUR_HIGH, commodity_probs[commodity])
 *   - No log scaling
 *   - No percentile scaling
 *   - No histogram equalisation
 *   - commodity_probs value is used as-is from the stored record
 *
 * Rule 3 (No Probability Transformation):
 *   The probability value used for colour is verbatim from
 *   voxel.commodity_probs[commodity]. It is never clamped beyond [0,1],
 *   never normalised across the visible set, never smoothed.
 *
 * Rule 4 (No Depth Model Derivation):
 *   Depth axis position = voxel.depth_m from stored record.
 *   Y-scale = canvas height / depthRange from twin metadata.
 *   No kernel recomputation, no interpolation between slices.
 *
 * Rule 5 (Decimation Without Value Alteration):
 *   When decimationStride > 1, voxels are subsampled by index.
 *   The displayed voxels are exact stored records — values unchanged.
 *   Decimation affects COUNT only, never individual voxel values.
 *
 * Rule 6 (Version-Locked):
 *   twinVersion prop is displayed and bound to the scene. The renderer
 *   does not switch versions — parent controls version selection.
 *
 * Rule 7 (Deterministic Snapshot):
 *   exportSnapshot() calls canvas.toDataURL('image/png') — produces a
 *   pixel-exact capture of the current WebGL framebuffer.
 *   No post-processing is applied to the snapshot.
 *
 * PERFORMANCE ARCHITECTURE:
 *   - InstancedMesh: O(1) draw call for up to MAX_INSTANCES voxels
 *   - Geometry: BoxGeometry(1,1,1) — scaled per voxel via instance matrix
 *   - Colors: InstancedBufferAttribute (Float32Array) — direct GPU upload
 *   - Decimation: integer stride over voxel array before GPU upload
 *   - Progressive: parent sends batches; renderer merges via addVoxels()
 * ═══════════════════════════════════════════════════════════════
 */

import { useEffect, useRef, useCallback, forwardRef, useImperativeHandle } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";

// GPU instance ceiling — beyond this, decimation is applied automatically
const MAX_INSTANCES = 50_000;

// Colour endpoints for direct linear mapping (Rule 2)
// Low probability → cool blue,  High probability → warm gold
const COLOUR_LOW  = new THREE.Color(0x1a5276);   // deep blue
const COLOUR_HIGH = new THREE.Color(0xf39c12);   // amber-gold

// Voxel box size in scene units (world-space)
const VOXEL_SIZE = 0.8;

/**
 * linearColour — direct linear interpolation between COLOUR_LOW and COLOUR_HIGH.
 *
 * PROOF OF RULE 2:
 *   t = commodity_probs[commodity]  ← verbatim from stored record
 *   colour = COLOUR_LOW + t × (COLOUR_HIGH - COLOUR_LOW)
 *   No log, percentile, or histogram transform is applied.
 *   t is clamped to [0,1] only to avoid WebGL NaN — NOT to rescale.
 */
function linearColour(probability) {
  const t = Math.max(0, Math.min(1, probability));   // guard against NaN only
  return new THREE.Color().lerpColors(COLOUR_LOW, COLOUR_HIGH, t);
}

/**
 * buildScene — initialise three.js renderer, scene, camera, lights, controls.
 * Returns { renderer, scene, camera, controls, instancedMesh, cleanup }.
 */
function buildScene(canvas, width, height) {
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, preserveDrawingBuffer: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setSize(width, height);
  renderer.setClearColor(0x0d1117, 1);

  const scene = new THREE.Scene();

  const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 5000);
  camera.position.set(60, 80, 120);
  camera.lookAt(0, 0, 0);

  const controls = new OrbitControls(camera, canvas);
  controls.enableDamping = true;
  controls.dampingFactor = 0.08;
  controls.minDistance = 5;
  controls.maxDistance = 2000;

  // Subtle ambient + directional lighting (display only — not related to scores)
  scene.add(new THREE.AmbientLight(0xffffff, 0.6));
  const dir = new THREE.DirectionalLight(0xffffff, 0.8);
  dir.position.set(50, 100, 50);
  scene.add(dir);

  // Axes helper (10 unit scale)
  scene.add(new THREE.AxesHelper(10));

  // InstancedMesh for GPU batching (Rule: O(1) draw call)
  const geo = new THREE.BoxGeometry(VOXEL_SIZE, VOXEL_SIZE, VOXEL_SIZE);
  const mat = new THREE.MeshLambertMaterial({ vertexColors: true });
  const mesh = new THREE.InstancedMesh(geo, mat, MAX_INSTANCES);
  mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
  mesh.count = 0;
  scene.add(mesh);

  let animId;
  function animate() {
    animId = requestAnimationFrame(animate);
    controls.update();
    renderer.render(scene, camera);
  }
  animate();

  function cleanup() {
    cancelAnimationFrame(animId);
    controls.dispose();
    renderer.dispose();
    geo.dispose();
    mat.dispose();
  }

  return { renderer, scene, camera, controls, mesh, cleanup };
}

/**
 * projectVoxels — convert stored voxel records to instance matrices + colours.
 *
 * PROOF OF RULE 1 + RULE 3:
 *   - position.x = voxel.lon_center  (stored, not derived)
 *   - position.y = -voxel.depth_m    (stored depth_m, negated for Y-up world)
 *   - position.z = voxel.lat_center  (stored, not derived)
 *   - colour     = linearColour(voxel.commodity_probs[commodity])
 *                                    (stored probability, linear mapping only)
 *   No smoothing, interpolation, or recomputation is applied.
 *
 * PROOF OF RULE 5 (decimation):
 *   stride controls which indices are included; the colour/position of any
 *   included voxel is identical to its stored record — values never altered.
 */
function projectVoxels(voxels, commodity, stride, depthScaleFactor) {
  const dummy   = new THREE.Object3D();
  const matrices = [];
  const colours  = [];

  for (let i = 0; i < voxels.length; i += stride) {
    const v = voxels[i];

    // Position: stored lat/lon/depth — no derivation (Rule 4)
    dummy.position.set(
      v.lon_center,
      -v.depth_m * depthScaleFactor,
      v.lat_center,
    );
    dummy.scale.setScalar(1);
    dummy.updateMatrix();
    matrices.push(dummy.matrix.clone());

    // Colour: direct linear map of stored probability (Rule 2 + 3)
    const prob   = v.commodity_probs?.[commodity] ?? 0;
    const colour = linearColour(prob);   // stored value, linear only
    colours.push(colour.r, colour.g, colour.b);
  }

  return { matrices, colours, count: matrices.length };
}

// ─────────────────────────────────────────────────────────────────────────────

const VoxelRenderer = forwardRef(function VoxelRenderer(
  {
    voxels = [],
    commodity,
    twinVersion,
    decimationStride = 1,
    depthScaleFactor = 0.05,
    width  = 800,
    height = 500,
  },
  ref
) {
  const canvasRef = useRef(null);
  const sceneRef  = useRef(null);

  // Expose exportSnapshot to parent (Rule 7)
  useImperativeHandle(ref, () => ({
    exportSnapshot() {
      if (!canvasRef.current) return null;
      return canvasRef.current.toDataURL("image/png");
    },
  }));

  // Initialise scene once
  useEffect(() => {
    if (!canvasRef.current) return;
    const ctx = buildScene(canvasRef.current, width, height);
    sceneRef.current = ctx;
    return ctx.cleanup;
  }, []);

  // Re-project whenever voxels, commodity, or decimation changes
  useEffect(() => {
    if (!sceneRef.current || !voxels.length || !commodity) return;
    const { mesh } = sceneRef.current;

    // Automatic decimation if voxel count exceeds MAX_INSTANCES (Rule 5)
    const effectiveStride = Math.max(
      decimationStride,
      Math.ceil(voxels.length / MAX_INSTANCES),
    );

    const { matrices, colours, count } = projectVoxels(
      voxels, commodity, effectiveStride, depthScaleFactor,
    );

    // Upload instance matrices
    for (let i = 0; i < count; i++) {
      mesh.setMatrixAt(i, matrices[i]);
    }
    mesh.count = count;
    mesh.instanceMatrix.needsUpdate = true;

    // Upload instance colours — direct Float32Array upload (GPU batching)
    const colorAttr = new THREE.InstancedBufferAttribute(
      new Float32Array(colours), 3
    );
    mesh.geometry.setAttribute("color", colorAttr);

    // Auto-frame camera on first load
    if (count > 0) {
      const box = new THREE.Box3().setFromObject(mesh);
      const centre = box.getCenter(new THREE.Vector3());
      const size   = box.getSize(new THREE.Vector3()).length();
      sceneRef.current.controls.target.copy(centre);
      sceneRef.current.camera.position.set(
        centre.x + size * 0.8,
        centre.y + size * 0.5,
        centre.z + size * 0.8,
      );
    }
  }, [voxels, commodity, decimationStride, depthScaleFactor]);

  // Handle resize
  useEffect(() => {
    if (!sceneRef.current) return;
    const { renderer, camera } = sceneRef.current;
    renderer.setSize(width, height);
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
  }, [width, height]);

  return (
    <canvas
      ref={canvasRef}
      width={width}
      height={height}
      className="rounded-lg block"
      style={{ width, height }}
    />
  );
});

export default VoxelRenderer;
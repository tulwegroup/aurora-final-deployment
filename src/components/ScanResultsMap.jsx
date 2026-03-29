/**
 * ScanResultsMap — Leaflet map rendering scan cell results colored by tier/ACIF
 */
import { useEffect, useRef } from 'react';

const TIER_COLORS = {
  1: '#16a34a', // green — high prospectivity
  2: '#d97706', // amber — moderate
  3: '#dc2626', // red — low
};

export default function ScanResultsMap({ geojson, geometry }) {
  const mapRef = useRef(null);
  const leafletRef = useRef(null);

  useEffect(() => {
    if (!mapRef.current || leafletRef.current) return;

    import('leaflet').then(L => {
      delete L.Icon.Default.prototype._getIconUrl;
      const map = L.map(mapRef.current).setView([0, 0], 4);
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors', maxZoom: 18,
      }).addTo(map);

      leafletRef.current = map;

      const layers = [];

      // Draw AOI boundary if provided
      if (geometry?.coordinates) {
        const ring = geometry.coordinates[0].map(([lon, lat]) => [lat, lon]);
        const aoiLayer = L.polygon(ring, {
          color: '#3b82f6', weight: 2, fillOpacity: 0, dashArray: '6 4'
        }).addTo(map);
        layers.push(aoiLayer);
      }

      // Draw scan cells
      if (geojson?.features?.length > 0) {
        const cellLayers = L.featureGroup();
        for (const feat of geojson.features) {
          const tier = feat.properties?.tier || 3;
          const acif = feat.properties?.acif_score ?? 0;
          const color = TIER_COLORS[tier] || '#6b7280';
          const geomType = feat.geometry.type;
          const coords = feat.geometry.coordinates;
          let layer;

          if (geomType === 'Point') {
            const [lon, lat] = coords;
            layer = L.circleMarker([lat, lon], {
              radius: 4,
              color: '#1e293b',
              weight: 1,
              fillColor: color,
              fillOpacity: 0.7,
            });
          } else if (geomType === 'Polygon') {
            const ring = coords[0].map(([lon, lat]) => [lat, lon]);
            layer = L.polygon(ring, {
              color: '#1e293b', weight: 0.5,
              fillColor: color, fillOpacity: 0.6,
            });
          }

          if (layer) {
            layer.bindTooltip(
              `<div class="text-xs space-y-0.5">
                <div><b>Tier ${tier}</b></div>
                <div>ACIF: ${(acif * 100).toFixed(1)}%</div>
                <div>Clay: ${((feat.properties?.clay_index ?? 0) * 100).toFixed(1)}%</div>
                <div>Ferric: ${((feat.properties?.ferric_ratio ?? 0) * 100).toFixed(1)}%</div>
                <div class="text-slate-400">${feat.properties?.source || ''}</div>
              </div>`,
              { sticky: true }
            );
            cellLayers.addLayer(layer);
          }
        }
        cellLayers.addTo(map);
        layers.push(cellLayers);

        // Fit map to cells
        try { map.fitBounds(cellLayers.getBounds().pad(0.1)); } catch (_) {}
      } else if (geometry?.coordinates) {
        // Fit to AOI boundary
        const ring = geometry.coordinates[0].map(([lon, lat]) => [lat, lon]);
        try { map.fitBounds(L.polygon(ring).getBounds().pad(0.2)); } catch (_) {}
      }
    });

    return () => {
      if (leafletRef.current) { leafletRef.current.remove(); leafletRef.current = null; }
    };
  }, []);

  // Legend
  return (
    <div className="space-y-2">
      <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
      <div ref={mapRef} className="w-full rounded-lg border" style={{ height: 420 }} />
      <div className="flex gap-4 text-xs text-muted-foreground">
        {Object.entries(TIER_COLORS).map(([tier, color]) => (
          <div key={tier} className="flex items-center gap-1.5">
            <div className="w-3 h-3 rounded-sm border" style={{ background: color }} />
            <span>Tier {tier}</span>
          </div>
        ))}
        <div className="flex items-center gap-1.5">
          <div className="w-5 h-0.5 border-t-2 border-dashed border-blue-500" />
          <span>AOI</span>
        </div>
      </div>
    </div>
  );
}
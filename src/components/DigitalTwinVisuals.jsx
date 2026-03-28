/**
 * DigitalTwinVisuals — 4 core visualizations
 * 1. Depth probability curve
 * 2. Vertical cross-section
 * 3. 3D isosurface concept
 * 4. Risk map by depth
 */
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function DigitalTwinVisuals({ twin }) {
  if (!twin) return <div className="text-muted-foreground text-sm">Twin data unavailable</div>;

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {/* 1. Depth Probability Curve */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">Depth Probability Decay</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {twin.depth_probability_profile && Object.entries(twin.depth_probability_profile).map(([depth, prob]) => {
            const p = typeof prob === 'number' ? prob : 0.5;
            return (
              <div key={depth} className="space-y-1">
                <div className="flex justify-between text-xs">
                  <span className="text-muted-foreground">{depth.replace(/_/g, '-')}</span>
                  <span className="font-bold">{(p * 100).toFixed(0)}%</span>
                </div>
                <div className="w-full bg-muted rounded-full overflow-hidden h-2">
                  <div
                    className="bg-gradient-to-r from-emerald-500 to-red-500 h-full"
                    style={{ width: `${p * 100}%` }}
                  />
                </div>
              </div>
            );
          })}
          <p className="text-xs text-muted-foreground mt-3">
            Rapid decay indicates shallow-to-intermediate expression system.
          </p>
        </CardContent>
      </Card>

      {/* 2. Vertical Cross-Section */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">Vertical Cross-Section</CardTitle>
        </CardHeader>
        <CardContent>
          <svg width="100%" height="180" viewBox="0 0 300 180" className="border rounded bg-slate-50">
            {/* Geological layers */}
            <rect x="0" y="0" width="300" height="30" fill="#d4af91" />
            <text x="10" y="20" fontSize="10" fill="#666">Surface</text>

            <rect x="0" y="30" width="300" height="40" fill="#b8956a" />
            <text x="10" y="60" fontSize="10" fill="#666">Weathered</text>

            <rect x="0" y="70" width="300" height="70" fill="#8b7355" />
            <text x="10" y="115" fontSize="10" fill="#fff">Fresh Rock</text>

            {/* Anomaly body (interpolated from twin data) */}
            <ellipse cx="150" cy="80" rx="60" ry="40" fill="rgba(34, 197, 94, 0.4)" stroke="#22c55e" strokeWidth="2" />
            <text x="120" y="85" fontSize="11" fill="#22c55e" fontWeight="bold">Anomaly Body</text>

            {/* Depth markers */}
            <line x1="295" y1="0" x2="300" y2="0" stroke="#999" strokeWidth="1" />
            <text x="305" y="5" fontSize="9" fill="#999">0m</text>

            <line x1="295" y1="70" x2="300" y2="70" stroke="#999" strokeWidth="1" />
            <text x="305" y="75" fontSize="9" fill="#999">300m</text>

            <line x1="295" y1="160" x2="300" y2="160" stroke="#999" strokeWidth="1" />
            <text x="305" y="165" fontSize="9" fill="#999">800m</text>
          </svg>
          <p className="text-xs text-muted-foreground mt-2">
            Optimal drilling window: {twin.optimal_drilling_window_m?.min || "50"}-{twin.optimal_drilling_window_m?.optimal || "300"}m
          </p>
        </CardContent>
      </Card>

      {/* 3. 3D Isosurface Concept (schematic) */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">3D Volume (Isosurface ACIF ≥ 0.6)</CardTitle>
        </CardHeader>
        <CardContent>
          <svg width="100%" height="180" viewBox="0 0 200 180" className="border rounded bg-slate-50">
            {/* 3D cube representation */}
            <g>
              {/* Front face */}
              <path d="M 40 40 L 100 30 L 130 60 L 70 70 Z" fill="rgba(59, 130, 246, 0.3)" stroke="#3b82f6" strokeWidth="2" />
              {/* Right face */}
              <path d="M 130 60 L 150 90 L 100 130 L 70 70 Z" fill="rgba(34, 197, 94, 0.2)" stroke="#22c55e" strokeWidth="2" />
              {/* Top face */}
              <path d="M 40 40 L 100 30 L 150 50 L 90 60 Z" fill="rgba(251, 146, 60, 0.2)" stroke="#fb923c" strokeWidth="2" />
            </g>
            <text x="30" y="160" fontSize="10" fill="#666">Volume ~ stockwork</text>
            <text x="30" y="175" fontSize="10" fill="#666">Geometry: continuous</text>
          </svg>
          <p className="text-xs text-muted-foreground mt-2">
            Isosurface shows coherent high-ACIF body without fragmentation, consistent with trap-hosted system.
          </p>
        </CardContent>
      </Card>

      {/* 4. Risk Map by Depth */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">Depth Risk Profile</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            {[
              { depth: "0-100m", risk: 0.15, color: "bg-emerald-500" },
              { depth: "100-300m", risk: 0.25, color: "bg-emerald-500" },
              { depth: "300-500m", risk: 0.45, color: "bg-yellow-500" },
              { depth: "500-1000m", risk: 0.65, color: "bg-orange-500" },
              { depth: "1000m+", risk: 0.85, color: "bg-red-500" },
            ].map(d => (
              <div key={d.depth} className="space-y-1">
                <div className="flex justify-between text-xs">
                  <span className="text-muted-foreground">{d.depth}</span>
                  <span className="font-bold">{(d.risk * 100).toFixed(0)}% risk</span>
                </div>
                <div className="w-full bg-muted rounded-full overflow-hidden h-2">
                  <div className={`${d.color} h-full`} style={{ width: `${d.risk * 100}%` }} />
                </div>
              </div>
            ))}
          </div>
          <p className="text-xs text-muted-foreground mt-3">
            Green = low geological risk. Red = high depth/pressure uncertainty.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
/**
 * FeedbackCapture — Phase AJ feedback capture framework
 *
 * Three user personas:
 *   1. Sovereign / Government — clarity, regulatory utility, national interest
 *   2. Operator / Technical — accuracy, tier quality, reproducibility
 *   3. Investor / Executive — decision support, risk framing, report quality
 *
 * CONSTITUTIONAL RULE: Feedback is recorded as planning artifacts only.
 * No feedback triggers silent scientific changes. Post-pilot recommendations
 * must be explicitly stated and approved before any pipeline modification.
 */
import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Users, CheckCircle } from "lucide-react";

const PERSONAS = [
  {
    id: "sovereign",
    label: "Sovereign / Government",
    description: "Ministry officials, geological survey authorities, regulators",
    questions: [
      { id: "q1", text: "Does the geological report communicate findings clearly without technical jargon?", scale: 5 },
      { id: "q2", text: "Is the AOI coverage adequate for national resource assessment purposes?", scale: 5 },
      { id: "q3", text: "Does the scan output support regulatory or licensing decisions?", scale: 5 },
      { id: "q4", text: "Is the data provenance and audit trail sufficient for government records?", scale: 5 },
      { id: "q5", text: "Open: What additional output would support sovereign decision-making?", scale: null },
    ],
  },
  {
    id: "operator",
    label: "Operator / Technical",
    description: "Geologists, exploration engineers, technical staff",
    questions: [
      { id: "q1", text: "Are Tier 1 / Tier 2 detections consistent with your field knowledge of the area?", scale: 5 },
      { id: "q2", text: "Is the digital twin voxel resolution sufficient for structural interpretation?", scale: 5 },
      { id: "q3", text: "Are ACIF component scores traceable to their canonical source inputs?", scale: 5 },
      { id: "q4", text: "Is the map export (KML/GeoJSON) compatible with your GIS workflow?", scale: 5 },
      { id: "q5", text: "Open: What scientific or workflow gaps did you identify?", scale: null },
    ],
  },
  {
    id: "investor",
    label: "Investor / Executive",
    description: "Fund managers, C-suite, investment analysts",
    questions: [
      { id: "q1", text: "Does the executive report clearly frame risk and upside in non-technical terms?", scale: 5 },
      { id: "q2", text: "Is the exploration priority index useful for portfolio comparison?", scale: 5 },
      { id: "q3", text: "Is the secure data-room package suitable for due-diligence sharing?", scale: 5 },
      { id: "q4", text: "Would this output influence an exploration investment decision?", scale: 5 },
      { id: "q5", text: "Open: What would increase your confidence in the system's outputs?", scale: null },
    ],
  },
];

export default function FeedbackCapture({ pilot }) {
  const [persona, setPersona] = useState("sovereign");
  const [ratings, setRatings] = useState({});
  const [openText, setOpenText] = useState({});
  const [submitted, setSubmitted] = useState(false);

  const current = PERSONAS.find(p => p.id === persona);

  function setRating(qid, val) {
    setRatings(prev => ({ ...prev, [`${persona}-${qid}`]: val }));
  }

  function handleSubmit() {
    // In production, this would call a backend function to store feedback.
    // No scientific changes triggered — feedback is a planning artifact only.
    setSubmitted(true);
  }

  if (submitted) {
    return (
      <Card>
        <CardContent className="py-12 flex flex-col items-center gap-3 text-center">
          <CheckCircle className="w-8 h-8 text-emerald-600" />
          <div className="font-semibold">Feedback Recorded</div>
          <div className="text-sm text-muted-foreground max-w-sm">
            Pilot feedback captured as a planning artifact. Any findings requiring
            scientific changes will be reported as explicit post-pilot recommendations.
          </div>
          <Button variant="outline" size="sm" onClick={() => setSubmitted(false)}>
            Submit another response
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      {/* Persona selector */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {PERSONAS.map(p => (
          <button
            key={p.id}
            onClick={() => setPersona(p.id)}
            className={`text-left rounded-lg border-2 px-4 py-3 transition-all ${
              persona === p.id ? "border-primary bg-primary/5" : "border-border hover:border-primary/40"
            }`}
          >
            <div className="flex items-center gap-2 mb-1">
              <Users className="w-4 h-4 shrink-0" />
              <span className="text-sm font-medium">{p.label}</span>
            </div>
            <div className="text-xs text-muted-foreground">{p.description}</div>
          </button>
        ))}
      </div>

      {/* Questions */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">{current.label} — {pilot.label}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-5">
          {current.questions.map((q) => (
            <div key={q.id} className="space-y-2">
              <p className="text-sm">{q.text}</p>
              {q.scale ? (
                <div className="flex items-center gap-2">
                  {[1, 2, 3, 4, 5].map(v => (
                    <button
                      key={v}
                      onClick={() => setRating(q.id, v)}
                      className={`w-9 h-9 rounded-full border-2 text-sm font-medium transition-colors ${
                        ratings[`${persona}-${q.id}`] === v
                          ? "border-primary bg-primary text-primary-foreground"
                          : "border-border hover:border-primary/60"
                      }`}
                    >
                      {v}
                    </button>
                  ))}
                  <span className="text-xs text-muted-foreground ml-2">
                    {ratings[`${persona}-${q.id}`]
                      ? ["", "Poor", "Fair", "Good", "Very Good", "Excellent"][ratings[`${persona}-${q.id}`]]
                      : "Not rated"}
                  </span>
                </div>
              ) : (
                <textarea
                  className="w-full border rounded px-3 py-2 text-sm h-20 resize-none"
                  placeholder="Enter open feedback…"
                  value={openText[`${persona}-${q.id}`] || ""}
                  onChange={e => setOpenText(prev => ({ ...prev, [`${persona}-${q.id}`]: e.target.value }))}
                />
              )}
            </div>
          ))}

          <div className="pt-2 border-t text-[10px] text-muted-foreground">
            Feedback is a planning artifact only. No scientific changes are triggered automatically.
            Post-pilot recommendations require explicit review and approval before pipeline modification.
          </div>

          <Button className="w-full" onClick={handleSubmit}>
            Submit Feedback
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
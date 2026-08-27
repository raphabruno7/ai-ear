"use client";

import { useState } from "react";

// Stand-in for the client's scheduling system. The Chrome extension fills the
// inputs tagged data-copilot-field=... as the copilot extracts them.

const FIELDS: { name: string; label: string; type?: string }[] = [
  { name: "owner_name", label: "Owner name" },
  { name: "owner_phone", label: "Owner phone", type: "tel" },
  { name: "owner_email", label: "Owner email", type: "email" },
  { name: "pet_name", label: "Pet name" },
  { name: "visit_type", label: "Visit type" },
  { name: "preferred_time", label: "Preferred time" },
];

export default function DemoScheduler() {
  const [values, setValues] = useState<Record<string, string>>({});
  const set = (k: string, v: string) => setValues((s) => ({ ...s, [k]: v }));

  return (
    <main style={{ maxWidth: 480, margin: "40px auto", fontFamily: "system-ui" }}>
      <h1 style={{ fontSize: 18 }}>Scheduling — new appointment</h1>
      <form>
        {FIELDS.map((f) => (
          <div key={f.name} style={{ margin: "12px 0" }}>
            <label style={{ display: "block", fontSize: 13, color: "#555" }}>{f.label}</label>
            <input
              data-copilot-field={f.name}
              type={f.type || "text"}
              value={values[f.name] || ""}
              onChange={(e) => set(f.name, e.target.value)}
              style={{ width: "100%", padding: 6, boxSizing: "border-box" }}
            />
          </div>
        ))}
        <textarea
          data-copilot-field="clinical_notes"
          placeholder="Clinical notes"
          value={values.clinical_notes || ""}
          onChange={(e) => set("clinical_notes", e.target.value)}
          rows={3}
          style={{ width: "100%", padding: 6, boxSizing: "border-box" }}
        />
      </form>
      <style>{`.copilot-filled { background: #f0fdf4; }`}</style>
    </main>
  );
}

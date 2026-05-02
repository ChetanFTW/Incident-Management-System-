import { useState, useEffect } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { getIncident, submitRCA } from "../api/client";
import Navbar from "../components/Navbar";

const CATEGORIES = [
  "INFRASTRUCTURE","CODE_BUG","CONFIGURATION",
  "DEPENDENCY","CAPACITY","NETWORK","SECURITY","UNKNOWN",
];

export default function RCAForm() {
  const { id } = useParams();
  const nav    = useNavigate();
  const [inc, setInc]         = useState(null);
  const [submitting, setSub]  = useState(false);
  const [error, setError]     = useState("");
  const [form, setForm] = useState({
    incident_start: "", incident_end: "",
    root_cause_category: "UNKNOWN",
    root_cause_description: "", fix_applied: "", prevention_steps: "",
  });

  useEffect(() => {
    getIncident(id).then(({ data }) => {
      setInc(data);
      if (data.first_signal_at)
        setForm((f) => ({ ...f, incident_start: data.first_signal_at.slice(0,16) }));
      if (data.resolved_at)
        setForm((f) => ({ ...f, incident_end: data.resolved_at.slice(0,16) }));
      if (data.rca) {
        setForm({
          incident_start:         data.rca.incident_start.slice(0,16),
          incident_end:           data.rca.incident_end.slice(0,16),
          root_cause_category:    data.rca.root_cause_category,
          root_cause_description: data.rca.root_cause_description,
          fix_applied:            data.rca.fix_applied,
          prevention_steps:       data.rca.prevention_steps,
        });
      }
    }).catch(() => nav("/"));
  }, [id]);

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  const submit = async (e) => {
    e.preventDefault();
    setError(""); setSub(true);
    try {
      await submitRCA(id, {
        ...form,
        incident_start: new Date(form.incident_start).toISOString(),
        incident_end:   new Date(form.incident_end).toISOString(),
      });
      nav(`/incidents/${id}`);
    } catch (err) {
      const d = err.response?.data?.detail;
      setError(Array.isArray(d) ? d.map((x) => x.msg).join(", ") : d || "Submit failed");
    } finally { setSub(false); }
  };

  if (!inc) return <div className="page"><div className="loading">Loading...</div></div>;

  const textFields = [
    ["root_cause_description", "Root Cause Description", "Describe what caused this incident in detail (min 20 chars)..."],
    ["fix_applied",            "Fix Applied",            "What change or action resolved the incident?"],
    ["prevention_steps",       "Prevention Steps",       "What will prevent this from happening again?"],
  ];

  return (
    <div className="page">
      <Navbar wsConnected={false} />
      <div className="container" style={{ maxWidth: "720px" }}>
        <div className="breadcrumb">
          <Link to="/">Dashboard</Link><span>/</span>
          <Link to={`/incidents/${id}`}>{inc.component_id}</Link><span>/</span>
          <span>RCA</span>
        </div>

        <p className="form-title">Root Cause Analysis</p>
        <p className="form-sub">All fields mandatory · Minimum 20 characters for text areas</p>

        {error && <div className="alert alert-error">{error}</div>}

        <form onSubmit={submit} className="form-card">
          {/* Date pickers */}
          <div className="grid-2-form" style={{ marginBottom: "16px" }}>
            <div className="form-group">
              <label className="form-label">Incident Start <span className="req">*</span></label>
              <input type="datetime-local" className="form-input"
                value={form.incident_start} onChange={set("incident_start")} required />
            </div>
            <div className="form-group">
              <label className="form-label">Incident End <span className="req">*</span></label>
              <input type="datetime-local" className="form-input"
                value={form.incident_end} onChange={set("incident_end")} required />
            </div>
          </div>

          {/* Category */}
          <div className="form-group">
            <label className="form-label">Root Cause Category <span className="req">*</span></label>
            <select className="form-select" value={form.root_cause_category} onChange={set("root_cause_category")}>
              {CATEGORIES.map((c) => <option key={c}>{c}</option>)}
            </select>
          </div>

          {/* Text areas */}
          {textFields.map(([key, label, placeholder]) => (
            <div className="form-group" key={key}>
              <label className="form-label">{label} <span className="req">*</span></label>
              <textarea className="form-textarea" rows={4}
                value={form[key]} onChange={set(key)}
                required minLength={20} placeholder={placeholder} />
              <p className="char-count">{form[key].length} / 20 min chars</p>
            </div>
          ))}

          <div className="form-actions">
            <button type="submit" className="btn btn-blue" disabled={submitting} style={{ flex: 1 }}>
              {submitting ? "Submitting..." : inc.rca ? "Update RCA" : "Submit RCA"}
            </button>
            <Link to={`/incidents/${id}`} className="btn-cancel">Cancel</Link>
          </div>
        </form>
      </div>
    </div>
  );
}

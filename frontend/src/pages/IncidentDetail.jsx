import { useState, useEffect } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { getIncident, transitionState } from "../api/client";
import PriorityBadge from "../components/PriorityBadge";
import StatusBadge from "../components/StatusBadge";
import Navbar from "../components/Navbar";
import { format } from "date-fns";

const TRANSITIONS = {
  OPEN:          ["INVESTIGATING"],
  INVESTIGATING: ["RESOLVED"],
  RESOLVED:      ["CLOSED", "INVESTIGATING"],
  CLOSED:        [],
};

export default function IncidentDetail() {
  const { id } = useParams();
  const nav = useNavigate();
  const [inc, setInc]             = useState(null);
  const [loading, setLoading]     = useState(true);
  const [transitioning, setTransitioning] = useState(false);
  const [note, setNote]           = useState("");
  const [error, setError]         = useState("");

  const load = async () => {
    try {
      const { data } = await getIncident(id);
      setInc(data);
    } catch { nav("/"); }
    finally { setLoading(false); }
  };

  useEffect(() => { load(); }, [id]);

  const doTransition = async (to_status) => {
    setError(""); setTransitioning(true);
    try {
      await transitionState(id, to_status, note || undefined);
      setNote("");
      await load();
    } catch (e) {
      setError(e.response?.data?.detail || "Transition failed");
    } finally { setTransitioning(false); }
  };

  if (loading) return <div className="page"><div className="loading">Loading incident...</div></div>;
  if (!inc)    return null;

  const allowed = TRANSITIONS[inc.status] || [];
  const fmt = (d) => { try { return format(new Date(d), "HH:mm:ss"); } catch { return "—"; } };

  return (
    <div className="page">
      <Navbar wsConnected={false} />
      <div className="container">
        {/* Breadcrumb */}
        <div className="breadcrumb">
          <Link to="/">Dashboard</Link>
          <span>/</span>
          <span>{inc.component_id}</span>
        </div>

        {/* Main card */}
        <div className="detail-card">
          <div className="detail-header">
            <div style={{ flex: 1 }}>
              <div className="detail-badges">
                <PriorityBadge priority={inc.priority} />
                <StatusBadge status={inc.status} />
                <span style={{ fontSize: "12px", color: "#475569" }}>{inc.component_type}</span>
              </div>
              <h1 className="detail-title">{inc.title}</h1>
              {inc.description && <p className="detail-desc">{inc.description}</p>}
            </div>
            <div className="detail-meta">
              <span>Signals: <strong>{inc.total_signals ?? inc.signal_count}</strong></span>
              {inc.mttr_seconds && (
                <span>MTTR: <strong style={{ color: "#22c55e" }}>{Math.round(inc.mttr_seconds / 60)}m</strong></span>
              )}
              <span>Component: <strong>{inc.component_id}</strong></span>
            </div>
          </div>

          {/* Transition controls */}
          {allowed.length > 0 && (
            <div className="transition-bar">
              <p>Transition state →</p>
              <div className="transition-actions">
                {allowed.map((s) => (
                  <button key={s} className="btn btn-ghost btn-sm"
                    onClick={() => doTransition(s)} disabled={transitioning}>
                    → {s}
                  </button>
                ))}
                <input className="transition-input" value={note}
                  onChange={(e) => setNote(e.target.value)}
                  placeholder="Optional note..." />
              </div>
              {error && <div className="alert alert-error" style={{ marginTop: "12px" }}>{error}</div>}
            </div>
          )}

          {/* RCA CTA */}
          {inc.status === "RESOLVED" && (
            <div className="rca-prompt">
              <Link to={`/incidents/${id}/rca`} className="btn btn-blue btn-sm">
                {inc.rca ? "✏️ Edit RCA" : "📝 Submit RCA"}
              </Link>
              {!inc.rca && <span className="warn-text">⚠ RCA required before closing</span>}
            </div>
          )}
        </div>

        {/* Grid: timeline + signals */}
        <div className="grid-2">
          {/* Timeline */}
          <div className="detail-card">
            <p className="section-title">State Timeline</p>
            <div className="timeline">
              {(inc.transitions || []).length === 0 && (
                <p style={{ color: "#475569", fontSize: "13px" }}>No transitions yet</p>
              )}
              {(inc.transitions || []).map((t, i) => (
                <div key={t.id || i} className="timeline-item">
                  <span className="timeline-time">{fmt(t.transitioned_at)}</span>
                  <div>
                    <span style={{ color: "#475569" }}>{t.from_status || "—"}</span>
                    <span className="timeline-arrow"> → </span>
                    <span className="timeline-status">{t.to_status}</span>
                    {t.note && <div className="timeline-note">{t.note}</div>}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Raw signals */}
          <div className="detail-card">
            <p className="section-title">Raw Signals <span style={{ color: "#475569", fontWeight: 400 }}>(latest 50 from MongoDB)</span></p>
            <div className="signal-list">
              {(inc.raw_signals || []).length === 0 && (
                <p style={{ color: "#475569", fontSize: "13px" }}>No signals found</p>
              )}
              {(inc.raw_signals || []).map((s, i) => (
                <div key={i} className="signal-item">
                  <div className="signal-top">
                    <span className={`signal-sev-${s.severity}`}>{s.severity}</span>
                    <span className="signal-time">{fmt(s.received_at)}</span>
                  </div>
                  <div className="signal-msg">{s.message}</div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* RCA display */}
        {inc.rca && (
          <div className="rca-card">
            <p className="rca-title">📋 Root Cause Analysis</p>
            <div className="rca-grid">
              <div className="rca-field">
                <p>Category</p>
                <p>{inc.rca.root_cause_category}</p>
              </div>
              <div className="rca-field">
                <p>Duration</p>
                <p>
                  {format(new Date(inc.rca.incident_start), "MMM d HH:mm")} →{" "}
                  {format(new Date(inc.rca.incident_end), "HH:mm")}
                </p>
              </div>
              <div className="rca-field full">
                <p>Root Cause</p>
                <p>{inc.rca.root_cause_description}</p>
              </div>
              <div className="rca-field">
                <p>Fix Applied</p>
                <p>{inc.rca.fix_applied}</p>
              </div>
              <div className="rca-field">
                <p>Prevention Steps</p>
                <p>{inc.rca.prevention_steps}</p>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

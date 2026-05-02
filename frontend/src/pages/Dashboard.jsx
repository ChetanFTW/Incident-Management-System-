import { useState, useCallback, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { getIncidents } from "../api/client";
import { useWebSocket } from "../hook/useWebSocket";
import PriorityBadge from "../components/PriorityBadge";
import StatusBadge from "../components/StatusBadge";
import Navbar from "../components/Navbar";
import { formatDistanceToNow } from "date-fns";
import "./Dashboard.css";

const FILTERS = ["ALL", "OPEN", "INVESTIGATING", "RESOLVED", "CLOSED"];

export default function Dashboard() {
  const nav = useNavigate();
  const [incidents, setIncidents] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("ALL");
  const [page, setPage] = useState(1);

  const fetchIncidents = useCallback(async () => {
    setLoading(true);
    try {
      const params = { page, page_size: 20 };
      if (filter !== "ALL") params.status = filter;
      const { data } = await getIncidents(params);
      setIncidents(data.items);
      setTotal(data.total);
    } catch (e) {
      console.error("Failed to fetch incidents:", e);
    } finally {
      setLoading(false);
    }
  }, [filter, page]);

  useEffect(() => {
    fetchIncidents();
  }, [fetchIncidents]);

  const onWsMessage = useCallback(
    (msg) => {
      if (
        ["snapshot", "incident_created", "incident_updated"].includes(msg.type)
      ) {
        fetchIncidents();
      }
    },
    [fetchIncidents]
  );

  const wsConnected = useWebSocket(onWsMessage);

  const priorityOrder = { P0: 0, P1: 1, P2: 2 };
  const sorted = [...incidents].sort(
    (a, b) =>
      (priorityOrder[a.priority] ?? 9) -
      (priorityOrder[b.priority] ?? 9)
  );

  const handleFilter = (f) => {
    setFilter(f);
    setPage(1);
  };

  return (
    <div className="page">
      <Navbar wsConnected={wsConnected} />

      <div className="container">
        {/* Header */}
        <div className="dashboard-header">
          <h1 className="dashboard-title">Incident Dashboard</h1>
          <p className="dashboard-sub">{total} total incidents</p>
        </div>

        {/* Filters */}
        <div className="filter-bar">
          {FILTERS.map((f) => (
            <button
              key={f}
              className={`filter-btn ${filter === f ? "active" : ""}`}
              onClick={() => handleFilter(f)}
            >
              {f}
            </button>
          ))}
        </div>

        {/* Content */}
        {loading ? (
          <div className="loading">Loading incidents...</div>
        ) : sorted.length === 0 ? (
          <div className="empty-state">
            <div className="icon">✅</div>
            <p>No incidents found for this filter.</p>
          </div>
        ) : (
          <div className="card">
            <table>
              <thead>
                <tr>
                  <th>Priority</th>
                  <th>Component</th>
                  <th>Title</th>
                  <th>Status</th>
                  <th className="right">Signals</th>
                  <th className="right">First seen</th>
                </tr>
              </thead>

              <tbody>
                {sorted.map((inc) => (
                  <tr
                    key={inc.id}
                    onClick={() => nav(`/incidents/${inc.id}`)}
                  >
                    <td>
                      <PriorityBadge priority={inc.priority} />
                    </td>
                    <td className="td-mono">{inc.component_id}</td>
                    <td className="td-title">{inc.title}</td>
                    <td>
                      <StatusBadge status={inc.status} />
                    </td>
                    <td className="right">{inc.signal_count}</td>
                    <td className="right td-muted">
                      {formatDistanceToNow(
                        new Date(inc.first_signal_at),
                        { addSuffix: true }
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            {/* Pagination */}
            <div className="pagination">
              <button
                onClick={() =>
                  setPage((p) => Math.max(1, p - 1))
                }
                disabled={page === 1}
              >
                ← Prev
              </button>

              <span>
                Page {page} of{" "}
                {Math.max(1, Math.ceil(total / 20))}
              </span>

              <button
                onClick={() => setPage((p) => p + 1)}
                disabled={incidents.length < 20}
              >
                Next →
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
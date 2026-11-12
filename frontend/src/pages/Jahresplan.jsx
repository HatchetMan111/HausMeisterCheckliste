import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api, MONTH_SHORT } from "../api.js";
import { PlanRow } from "../components/ui.jsx";
import { useToast } from "../toast.jsx";
import { useReloadKey } from "../useQueueSync.js";

const PRIORITY_FILTERS = [
  { value: "all", label: "Alle" },
  { value: "high", label: "⚡ Wichtig" },
  { value: "normal", label: "⏱ Empfohlen" },
  { value: "low", label: "📌 Optional" },
  { value: "tip", label: "💡 Smart-Tipps" },
];

export default function Jahresplan() {
  const [params, setParams] = useSearchParams();
  const showToast = useToast();
  const reloadKey = useReloadKey();
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [busyMonth, setBusyMonth] = useState(null);

  const view = params.get("view") === "year" ? "year" : "month";
  const month = Number(params.get("month")) || new Date().getMonth() + 1;
  const priority = params.get("priority") || "all";

  useEffect(() => {
    let alive = true;
    api
      .get(`/api/maintenance/jahresplan?view=${view}&month=${month}&priority=${priority}`)
      .then((d) => alive && (setData(d), setError(null)))
      .catch((err) => alive && setError(err.message));
    return () => {
      alive = false;
    };
  }, [view, month, priority, reloadKey]);

  function setParam(key, value) {
    const next = new URLSearchParams(params);
    if (value === null) next.delete(key);
    else next.set(key, value);
    setParams(next);
  }

  async function monthAction(m, action) {
    setBusyMonth(m);
    try {
      const res = await api.post(`/api/maintenance/${action}-month/${m}`);
      showToast(
        action === "complete"
          ? `Monat abgehakt (${res.completed} Aufgabe(n)) ✓`
          : `Monat zurückgesetzt (${res.reopened})`
      );
      setData(await api.get(`/api/maintenance/jahresplan?view=${view}&month=${month}&priority=${priority}`));
    } catch (err) {
      showToast(err.message, true);
    } finally {
      setBusyMonth(null);
    }
  }

  if (error) return <div className="card flash error">{error}</div>;
  if (!data) return <p className="empty">Lade Jahresplan …</p>;

  return (
    <>
      <div className="page-head">
        <h1>📋 Jahres-Checkliste {data.year}</h1>
      </div>

      <div className="card filter-card">
        <div className="filter-group">
          <span className="muted">Ansicht:</span>
          <button className={"btn small" + (view === "month" ? " active" : "")} onClick={() => setParam("view", "month")}>
            📅 Monatsansicht
          </button>
          <button className={"btn small" + (view === "year" ? " active" : "")} onClick={() => setParam("view", "year")}>
            📋 Jahresübersicht
          </button>
        </div>
        <div className="filter-group">
          <span className="muted">Filter:</span>
          {PRIORITY_FILTERS.map((f) => (
            <button
              key={f.value}
              className={"btn small" + (priority === f.value ? " active" : "")}
              onClick={() => setParam("priority", f.value)}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      <div className="stats-row">
        <span className="stat"><strong>{data.total}</strong> Aufgaben</span>
        <span className="stat stat-ok"><strong>{data.done_total}</strong> erledigt ✓</span>
        <span className="stat"><strong>{data.open_total}</strong> noch offen</span>
      </div>

      {view === "month" && (
        <div className="card monthtabs">
          {MONTH_SHORT.map((name, idx) => (
            <button
              key={name}
              className={"btn small" + (idx + 1 === month ? " active" : "")}
              onClick={() => setParam("month", String(idx + 1))}
            >
              {name}
            </button>
          ))}
        </div>
      )}

      {data.months.map((mrow) => (
        <section className="card month-section" key={mrow.month}>
          <div className="month-head">
            <h2>{mrow.name}</h2>
            <div className="month-actions">
              <button className="btn small primary" disabled={busyMonth === mrow.month} onClick={() => monthAction(mrow.month, "complete")}>
                ✓ Alle abhaken
              </button>
              <button className="btn small" disabled={busyMonth === mrow.month} onClick={() => monthAction(mrow.month, "reopen")}>
                ↺ Zurücksetzen
              </button>
            </div>
          </div>
          {mrow.items.length > 0 ? (
            <ul className="task-list">
              {mrow.items.map((item) => (
                <PlanRow key={item.task_id} item={item} />
              ))}
            </ul>
          ) : (
            <p className="empty">Keine Aufgaben in diesem Monat (bzw. für diesen Filter).</p>
          )}
        </section>
      ))}

      {data.running.length > 0 && (
        <section className="card month-section">
          <div className="month-head"><h2>Laufende / einmalige Aufgaben</h2></div>
          <ul className="task-list">
            {data.running.map((item) => (
              <PlanRow key={item.task_id} item={item} />
            ))}
          </ul>
        </section>
      )}
    </>
  );
}

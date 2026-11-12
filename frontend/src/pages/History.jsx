import { useEffect, useState } from "react";
import { api, formatDateTime } from "../api.js";
import { useReloadKey } from "../useQueueSync.js";

export default function History() {
  const reloadKey = useReloadKey();
  const [rows, setRows] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let alive = true;
    api
      .get("/api/maintenance/history?limit=200")
      .then((d) => alive && (setRows(d.completions), setError(null)))
      .catch((err) => alive && setError(err.message));
    return () => {
      alive = false;
    };
  }, [reloadKey]);

  if (error) return <div className="card flash error">{error}</div>;

  return (
    <>
      <h1>Verlauf</h1>
      <section className="card">
        {rows === null ? (
          <p className="empty">Lade Verlauf …</p>
        ) : rows.length === 0 ? (
          <p className="empty">Noch keine Erledigungen erfasst.</p>
        ) : (
          <ul className="task-list">
            {rows.map((c) => (
              <li className="task-item" key={c.id}>
                <div className="task-info">
                  <span className="task-title">{c.task_title || "—"}</span>
                  <span className="task-meta">
                    {formatDateTime(c.completed_at)}
                    {c.completed_by ? ` · von ${c.completed_by}` : ""}
                  </span>
                  {c.note && <span className="task-desc">{c.note}</span>}
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </>
  );
}

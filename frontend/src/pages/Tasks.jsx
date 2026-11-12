import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, formatDate } from "../api.js";
import { PriorityChip, TipBadge } from "../components/ui.jsx";
import { useReloadKey } from "../useQueueSync.js";
import { useToast } from "../toast.jsx";

export default function Tasks() {
  const showToast = useToast();
  const reloadKey = useReloadKey();
  const [areas, setAreas] = useState([]);
  const [tasks, setTasks] = useState(null);
  const [error, setError] = useState(null);
  const [filterArea, setFilterArea] = useState("");
  const [q, setQ] = useState("");
  const [showInactive, setShowInactive] = useState(false);

  useEffect(() => {
    api.get("/api/meta").then((m) => setAreas(m.areas)).catch(() => {});
  }, []);

  const load = useCallback(async () => {
    const p = new URLSearchParams();
    if (filterArea) p.set("area", filterArea);
    if (q) p.set("q", q);
    if (showInactive) p.set("active", "false");
    try {
      const data = await api.get("/api/tasks?" + p.toString());
      setTasks(data.tasks);
      setError(null);
    } catch (err) {
      setError(err.message);
    }
  }, [filterArea, q, showInactive]);

  useEffect(() => {
    // Suche erst nach kurzer Pause ausführen (Debouncing beim Tippen).
    const t = setTimeout(load, q ? 250 : 0);
    return () => clearTimeout(t);
  }, [load, reloadKey]);

  async function toggle(task) {
    try {
      await api.post(`/api/tasks/${task.id}/toggle`);
      showToast(task.active ? "Aufgabe deaktiviert." : "Aufgabe aktiviert.");
      load();
    } catch (err) {
      showToast(err.message, true);
    }
  }

  async function remove(task) {
    if (!window.confirm(`Aufgabe „${task.title}" inkl. Verlauf wirklich löschen?`)) return;
    try {
      await api.del(`/api/tasks/${task.id}`);
      showToast("Aufgabe gelöscht.");
      load();
    } catch (err) {
      showToast(err.message, true);
    }
  }

  if (error) return <div className="card flash error">{error}</div>;

  return (
    <>
      <div className="page-head">
        <h1>Aufgaben</h1>
        <Link className="btn primary" to="/tasks/new">+ Neue Aufgabe</Link>
      </div>

      <div className="card filter-card">
        <label className="filter-field">
          <span>Bereich</span>
          <select value={filterArea} onChange={(e) => setFilterArea(e.target.value)}>
            <option value="">Alle</option>
            {areas.map((a) => (
              <option key={a.slug} value={a.slug}>{a.name}</option>
            ))}
          </select>
        </label>
        <label className="filter-field grow">
          <span>Suche</span>
          <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Aufgabe suchen …" />
        </label>
        <label className="check">
          <input
            type="checkbox"
            checked={showInactive}
            onChange={(e) => setShowInactive(e.target.checked)}
          />
          Inaktive anzeigen
        </label>
      </div>

      <section className="card">
        {tasks === null ? (
          <p className="empty">Lade Aufgaben …</p>
        ) : tasks.length === 0 ? (
          <p className="empty">
            Keine Aufgaben gefunden. <Link to="/tasks/new">Neue Aufgabe anlegen</Link> oder
            Checkliste importieren (Einstellungen).
          </p>
        ) : (
          <ul className="task-list">
            {tasks.map((t) => (
              <li key={t.id} className={"task-item prio-" + t.priority + (t.active ? "" : " inactive")}>
                <div className="task-info">
                  <Link to={`/tasks/${t.id}/edit`} className="task-title">
                    {t.title}
                  </Link>
                  <span className="task-meta">
                    {t.area_name || "—"}
                    {t.category_name ? ` · ${t.category_name}` : ""}
                    {t.next_due ? ` · nächste Fälligkeit: ${formatDate(t.next_due)}` : ""}
                    {t.schedule_text ? ` · ${t.schedule_text}` : ""}
                  </span>
                </div>
                <div className="task-actions">
                  <PriorityChip priority={t.priority} />
                  {t.source === "tip" && <TipBadge />}
                  {t.source === "placeholder" && <span className="badge placeholder">Platzhalter</span>}
                  <span className={"badge " + (t.active ? "ok" : "")}>{t.active ? "aktiv" : "inaktiv"}</span>
                  <Link className="btn small" to={`/tasks/${t.id}/edit`}>Bearbeiten</Link>
                  <button type="button" className="btn small" onClick={() => toggle(t)}>
                    {t.active ? "Deaktivieren" : "Aktivieren"}
                  </button>
                  <button type="button" className="btn small danger" onClick={() => remove(t)}>
                    Löschen
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </>
  );
}

import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, MONTH_NAMES } from "../api.js";
import { useCompleteActions } from "../complete.jsx";
import { DashboardRow, SectionCard } from "../components/ui.jsx";
import { useReloadKey } from "../useQueueSync.js";

export default function Dashboard() {
  const { complete, skip } = useCompleteActions();
  const reloadKey = useReloadKey();
  const [sections, setSections] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    let alive = true;
    api
      .get("/api/maintenance/sections")
      .then((data) => alive && (setSections(data), setError(null)))
      .catch((err) => alive && setError(err.message));
    return () => {
      alive = false;
    };
  }, [reloadKey]);

  const onSkipAll = useCallback(async () => {
    if (!window.confirm(`Alle ${sections.overdue_total} überfälligen Aufgaben als übersprungen markieren?`)) return;
    setBusy(true);
    try {
      const res = await api.post("/api/maintenance/skip-all-overdue");
      setSections((s) => ({ ...s, urgent: [], overdue_total: 0 }));
      alert(`${res.skipped} überfällige Aufgaben übersprungen.`);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }, [sections]);

  if (error) return <div className="card flash error">{error}</div>;
  if (!sections) return <p className="empty">Lade Übersicht …</p>;

  const today = new Date();
  const weekdays = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"];
  const todayLong = `${weekdays[today.getDay() === 0 ? 6 : today.getDay() - 1]}, ${today.getDate()}. ${MONTH_NAMES[today.getMonth()]} ${today.getFullYear()}`;
  const monthTotal = sections.month_focus.length + sections.month_rest.length;
  const allClear = !sections.urgent.length && monthTotal === 0 && !sections.later.length;

  const secs = [
    { key: "urgent", tone: "urgent", title: "🔥 Jetzt dringend", sub: "Überfällig und heute fällig – zuerst dran", items: sections.urgent },
    { key: "month", tone: "month", title: `📅 ${MONTH_NAMES[today.getMonth()]} – im Fokus`, sub: "Wichtige und empfohlene Aufgaben dieses Monats", items: sections.month_focus },
    { key: "monthrest", tone: "rest", title: `📌 ${MONTH_NAMES[today.getMonth()]} – optional`, sub: "Niedrige Priorität, wenn Zeit bleibt", items: sections.month_rest },
    { key: "later", tone: "rest", title: "🗓️ Später", sub: "Nächste 30 Tage", items: sections.later },
  ];

  return (
    <>
      <div className="page-head">
        <h1>🏠 Wartungsübersicht</h1>
        <span className="muted-date">📅 {todayLong}</span>
      </div>

      {sections.overdue_total >= 10 && (
        <div className="card onboard-panel">
          <h3>🧹 Viel Rückstand entdeckt ({sections.overdue_total})</h3>
          <p>
            Kommt das von einer Erstinstallation oder Migration? Alte Monate kannst du bequem im{" "}
            <Link to="/jahresplan">Jahresplan</Link> je Monat abhaken – oder alle überfälligen
            Punkte hier auf einmal überspringen, um sauber zu starten:
          </p>
          <button type="button" className="btn" disabled={busy} onClick={onSkipAll}>
            ⤼ Alle überfälligen überspringen ({sections.overdue_total})
          </button>
          <p className="hint">Übersprungene Aufgaben verschwinden vom Dashboard und erscheinen zum nächsten Termin wieder.</p>
        </div>
      )}

      <div className="stats-row">
        <span className={"stat" + (sections.urgent.length ? " stat-urgent" : "")}>🔥 {sections.urgent.length} dringend</span>
        <span className="stat">📅 {monthTotal} diesen Monat</span>
        <span className="stat">🗓️ {sections.later.length} demnächst</span>
        {allClear && <span className="stat stat-ok">🎉 Alles erledigt!</span>}
      </div>

      {secs.map((s) => (
        <SectionCard
          key={s.key}
          tone={s.tone}
          title={s.title}
          subtitle={s.sub}
          count={s.items.length}
          empty={
            s.items.length === 0 && (s.key === "urgent" || s.key === "month") ? (
              <p className="empty">
                {s.key === "urgent" ? "🎉 Nichts dringend – gut gemacht!" : "☀️ Keine offenen Aufgaben mehr in diesem Monat."}
              </p>
            ) : null
          }
        >
          {s.items.length > 0 && (
            <ul className="task-list">
              {s.items.map((item) => (
                <DashboardRow
                  key={item.instance_id}
                  item={item}
                  busy={busy}
                  onComplete={(it) => complete(it.instance_id)}
                  onSkip={(it) => skip(it.instance_id)}
                />
              ))}
            </ul>
          )}
        </SectionCard>
      ))}
    </>
  );
}

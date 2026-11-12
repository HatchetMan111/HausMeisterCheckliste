import { useState } from "react";
import { Link } from "react-router-dom";
import { AREA_ICONS, PRIORITY_LABELS, formatDate } from "../api.js";
import { useCompleteActions } from "../complete.jsx";

export function PriorityChip({ priority }) {
  return <span className={"chip chip-" + priority}>{PRIORITY_LABELS[priority] || PRIORITY_LABELS.normal}</span>;
}

export function TipBadge() {
  return <span className="badge tip">💡 Smart-Tipp</span>;
}

export function StatusLine({ item }) {
  if (item.status === "overdue") {
    return <span className="dot dot-red">🔴 überfällig seit {formatDate(item.due_date)}</span>;
  }
  if (item.status === "due") {
    return item.month_based
      ? <span className="dot dot-amber">🟠 fällig diesen Monat</span>
      : <span className="dot dot-amber">🟠 heute fällig</span>;
  }
  return <span className="dot">📆 fällig {formatDate(item.due_date)}</span>;
}

export function MetaLine({ item }) {
  return (
    <span className="task-meta">
      {item.area_name || "—"}
      {item.category_name ? ` · ${item.category_name}` : ""}
      {item.window_end && item.status === "due" ? ` · Fenster bis ${formatDate(item.window_end)}` : ""}
      {item.estimated_minutes ? ` · ⏳ ca. ${item.estimated_minutes} Min.` : ""}
    </span>
  );
}

export function TaskIcon({ area }) {
  return <span className="task-icon" aria-hidden="true">{AREA_ICONS[area] || "🏠"}</span>;
}

export function SectionCard({ tone, title, subtitle, count, children, empty }) {
  return (
    <section className={"card section tone-" + tone}>
      <div className="section-head">
        <h2>{title} {typeof count === "number" && <span className="count">{count}</span>}</h2>
        {subtitle && <p className="section-sub">{subtitle}</p>}
      </div>
      {children}
      {empty}
    </section>
  );
}

export function DashboardRow({ item, onComplete, onSkip, busy }) {
  return (
    <li className={"task-item status-" + item.status + " prio-" + item.priority}>
      <div className="task-info">
        <span className="task-title">
          <TaskIcon area={item.area} /> {item.title}
        </span>
        <span className="task-meta-line">
          <StatusLine item={item} />
          <MetaLine item={item} />
        </span>
        {item.description && <span className="task-desc">{item.description}</span>}
      </div>
      <div className="task-actions">
        <PriorityChip priority={item.priority} />
        <button
          type="button"
          className="btn primary"
          disabled={busy}
          onClick={() => onComplete(item)}
        >
          ✓ Erledigt
        </button>
        {item.status === "overdue" && (
          <button type="button" className="btn" disabled={busy} onClick={() => onSkip(item)}>
            ⤼ Überspringen
          </button>
        )}
      </div>
    </li>
  );
}

export function PlanRow({ item }) {
  const { complete } = useCompleteActions();
  const [busy, setBusy] = useState(false);
  return (
    <li className={"task-item prio-" + item.priority}>
      <div className="task-info">
        <span className="task-title">{item.title}</span>
        {item.description && <span className="task-desc">{item.description}</span>}
        <span className="task-meta">
          {item.area_name || "—"}
          {item.category_name ? ` · ${item.category_name}` : ""}
          {item.window_end ? ` · Fenster bis ${formatDate(item.window_end)}` : ""}
          {item.schedule_text ? ` · ${item.schedule_text}` : ""}
          {item.overdue > 0 && (
            <> · <strong className="overdue-hint">{item.overdue} überfällig</strong></>
          )}
        </span>
      </div>
      <div className="task-actions">
        <PriorityChip priority={item.priority} />
        {item.is_tip && <TipBadge />}
        {item.status === "done" ? (
          <span className="badge ok">✓ erledigt</span>
        ) : item.open_id ? (
          <button
            type="button"
            className="btn small primary"
            disabled={busy}
            onClick={async () => {
              setBusy(true);
              await complete(item.open_id);
              setBusy(false);
            }}
          >
            Erledigt
          </button>
        ) : (
          <span className="badge">geplant</span>
        )}
        <Link className="btn small" to={`/tasks/${item.task_id}/edit`}>Bearbeiten</Link>
      </div>
    </li>
  );
}

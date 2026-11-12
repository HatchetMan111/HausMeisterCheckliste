import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, MONTH_SHORT } from "../api.js";
import { useToast } from "../toast.jsx";

const SCHEDULE_TYPES = [
  { value: "one_time", label: "Einmalig (festes Datum)" },
  { value: "interval_days", label: "Tages-Intervall" },
  { value: "annual_window", label: "Jährlich, Fenster" },
  { value: "annual_repeat", label: "Jährlich, feste Monate" },
];

const BLANK = {
  title: "",
  description: "",
  area: "",
  category: "",
  priority: "normal",
  schedule_type: "one_time",
  interval_days: "",
  window_start_month: "",
  window_end_month: "",
  repeat_months: [],
  repeat_day: 1,
  due_date: "",
  start_date: "",
  estimated_minutes: "",
};

export default function TaskForm() {
  const { id } = useParams();
  const isEdit = Boolean(id);
  const navigate = useNavigate();
  const showToast = useToast();
  const [areas, setAreas] = useState([]);
  const [categories, setCategories] = useState([]);
  const [form, setForm] = useState(BLANK);
  const [loaded, setLoaded] = useState(!isEdit);
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.get("/api/meta").then((m) => {
      setAreas(m.areas);
      setCategories(m.categories);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    if (!isEdit) return;
    api
      .get(`/api/tasks/${id}`)
      .then((t) => {
        setForm({
          title: t.title || "",
          description: t.description || "",
          area: t.area || "",
          category: t.category || "",
          priority: t.priority || "normal",
          schedule_type: t.schedule_type || "one_time",
          interval_days: t.interval_days || "",
          window_start_month: t.window_start_month || "",
          window_end_month: t.window_end_month || "",
          repeat_months: Array.isArray(t.repeat_months) ? t.repeat_months : [],
          repeat_day: t.repeat_day || 1,
          due_date: t.due_date || "",
          start_date: t.start_date || "",
          estimated_minutes: t.estimated_minutes || "",
        });
        setLoaded(true);
      })
      .catch((err) => setError(err.message));
  }, [id, isEdit]);

  function set(key, value) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  function toggleMonth(m) {
    setForm((f) => {
      const has = f.repeat_months.includes(m);
      const next = has ? f.repeat_months.filter((x) => x !== m) : [...f.repeat_months, m].sort((a, b) => a - b);
      return { ...f, repeat_months: next };
    });
  }

  async function submit(event) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    const payload = {
      title: form.title,
      description: form.description || null,
      area: form.area || null,
      category: form.category || null,
      priority: form.priority,
      schedule_type: form.schedule_type,
      interval_days: form.interval_days ? Number(form.interval_days) : null,
      window_start_month: form.window_start_month ? Number(form.window_start_month) : null,
      window_end_month: form.window_end_month ? Number(form.window_end_month) : null,
      repeat_months: form.repeat_months.length ? form.repeat_months : null,
      repeat_day: form.repeat_day ? Number(form.repeat_day) : 1,
      due_date: form.due_date || null,
      start_date: form.start_date || null,
      estimated_minutes: form.estimated_minutes ? Number(form.estimated_minutes) : null,
      active: true,
    };
    try {
      if (isEdit) {
        await api.put(`/api/tasks/${id}`, payload);
        showToast("Aufgabe gespeichert ✓");
      } else {
        await api.post("/api/tasks", payload);
        showToast("Aufgabe angelegt ✓");
      }
      navigate("/tasks");
    } catch (err) {
      setError(err.message);
      window.scrollTo({ top: 0, behavior: "smooth" });
    } finally {
      setSaving(false);
    }
  }

  if (!loaded && !error) return <p className="empty">Lade Aufgabe …</p>;

  return (
    <>
      <h1>{isEdit ? "Aufgabe bearbeiten" : "Neue Aufgabe"}</h1>
      {error && <div className="card flash error">{error}</div>}

      <form className="card form" onSubmit={submit}>
        <label>
          Titel *
          <input
            type="text"
            required
            maxLength={300}
            value={form.title}
            onChange={(e) => set("title", e.target.value)}
          />
        </label>

        <label>
          Beschreibung
          <textarea
            rows={3}
            value={form.description}
            onChange={(e) => set("description", e.target.value)}
          />
        </label>

        <div className="grid2">
          <label>
            Bereich
            <select value={form.area} onChange={(e) => set("area", e.target.value)}>
              <option value="">—</option>
              {areas.map((a) => (
                <option key={a.slug} value={a.slug}>{a.name}</option>
              ))}
            </select>
          </label>
          <label>
            Kategorie
            <input
              type="text"
              list="category-list"
              placeholder="z. B. heizung"
              value={form.category}
              onChange={(e) => set("category", e.target.value)}
            />
            <datalist id="category-list">
              {categories.map((c) => (
                <option key={c.slug} value={c.slug}>{c.name}</option>
              ))}
            </datalist>
          </label>
        </div>

        <div className="grid2">
          <label>
            Priorität
            <select value={form.priority} onChange={(e) => set("priority", e.target.value)}>
              <option value="high">Hoch</option>
              <option value="normal">Normal</option>
              <option value="low">Niedrig</option>
            </select>
          </label>
          <label>
            Geschätzte Dauer (Minuten)
            <input
              type="number"
              min={0}
              value={form.estimated_minutes}
              onChange={(e) => set("estimated_minutes", e.target.value)}
            />
          </label>
        </div>

        <label>
          Zeitplan-Typ
          <select value={form.schedule_type} onChange={(e) => set("schedule_type", e.target.value)}>
            {SCHEDULE_TYPES.map((t) => (
              <option key={t.value} value={t.value}>{t.label}</option>
            ))}
          </select>
        </label>

        {form.schedule_type === "one_time" && (
          <label>
            Fälligkeitsdatum
            <input
              type="date"
              value={form.due_date}
              onChange={(e) => set("due_date", e.target.value)}
            />
          </label>
        )}

        {form.schedule_type === "interval_days" && (
          <div className="grid2">
            <label>
              Intervall (Tage)
              <input
                type="number"
                min={1}
                value={form.interval_days}
                onChange={(e) => set("interval_days", e.target.value)}
              />
            </label>
            <label>
              Erste Fälligkeit / Anker
              <input
                type="date"
                value={form.start_date}
                onChange={(e) => set("start_date", e.target.value)}
              />
            </label>
          </div>
        )}

        {form.schedule_type === "annual_window" && (
          <div className="grid2">
            <label>
              Fenster von
              <select value={form.window_start_month} onChange={(e) => set("window_start_month", e.target.value)}>
                <option value="">—</option>
                {MONTH_SHORT.map((m, i) => (
                  <option key={m} value={i + 1}>{m}</option>
                ))}
              </select>
            </label>
            <label>
              Fenster bis
              <select value={form.window_end_month} onChange={(e) => set("window_end_month", e.target.value)}>
                <option value="">—</option>
                {MONTH_SHORT.map((m, i) => (
                  <option key={m} value={i + 1}>{m}</option>
                ))}
              </select>
            </label>
          </div>
        )}

        {form.schedule_type === "annual_repeat" && (
          <>
            <div className="month-picker">
              {MONTH_SHORT.map((m, i) => (
                <button
                  key={m}
                  type="button"
                  className={"btn small month-pick" + (form.repeat_months.includes(i + 1) ? " active" : "")}
                  onClick={() => toggleMonth(i + 1)}
                >
                  {m}
                </button>
              ))}
            </div>
            <label>
              Tag im Monat
              <input
                type="number"
                min={1}
                max={31}
                value={form.repeat_day}
                onChange={(e) => set("repeat_day", e.target.value)}
              />
            </label>
          </>
        )}

        <div className="form-actions">
          <button className="btn primary" type="submit" disabled={saving}>
            {saving ? "Speichern …" : "Speichern"}
          </button>
          <button className="btn" type="button" onClick={() => navigate("/tasks")}>
            Abbrechen
          </button>
        </div>
      </form>
    </>
  );
}

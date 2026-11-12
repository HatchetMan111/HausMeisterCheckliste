import { useEffect, useState } from "react";
import { api } from "../api.js";
import { useToast } from "../toast.jsx";

export default function Settings() {
  const showToast = useToast();
  const [meta, setMeta] = useState(null);
  const [s, setS] = useState(null);
  const [error, setError] = useState(null);
  const [smtpPassword, setSmtpPassword] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.get("/api/meta").then(setMeta).catch(() => {});
    api
      .get("/api/settings")
      .then((d) => {
        setS(d);
        setError(null);
      })
      .catch((err) => setError(err.message));
  }, []);

  if (error) return <div className="card flash error">{error}</div>;
  if (!s) return <p className="empty">Lade Einstellungen …</p>;

  function set(key, value) {
    setS((cur) => ({ ...cur, [key]: value }));
  }

  async function save() {
    setSaving(true);
    try {
      const payload = {
        property_name: s.property.name,
        property_address: s.property.address || "",
        email_enabled: s.channels.email,
        smtp_host: s.smtp.host,
        smtp_port: s.smtp.port,
        smtp_security: s.smtp.security,
        smtp_user: s.smtp.user,
        smtp_from: s.smtp.from,
        notify_email: s.notify_email,
        notify_days_ahead: Number(s.notify_days_ahead ?? 7),
      };
      if (smtpPassword) payload.smtp_password = smtpPassword;
      const updated = await api.put("/api/settings", payload);
      setS(updated);
      setSmtpPassword("");
      showToast("Einstellungen gespeichert ✓");
      return true;
    } catch (err) {
      showToast(err.message, true);
      return false;
    } finally {
      setSaving(false);
    }
  }

  async function testEmail() {
    // Zuerst speichern, damit der Test die eingegebenen Werte nutzt.
    const ok = await save();
    if (!ok) return;
    try {
      const res = await api.post("/api/settings/test-email", {});
      showToast(res.detail || "Test-E-Mail versendet ✓");
    } catch (err) {
      showToast(err.message, true);
    }
  }

  function urlBase64ToUint8Array(base64String) {
    const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
    const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
    const raw = window.atob(base64);
    const arr = new Uint8Array(raw.length);
    for (let i = 0; i < raw.length; i++) arr[i] = raw.charCodeAt(i);
    return arr;
  }

  async function subscribePush() {
    if (!("serviceWorker" in navigator) || !("PushManager" in window)) {
      showToast("Push wird von diesem Browser nicht unterstützt.", true);
      return;
    }
    try {
      const permission = await Notification.requestPermission();
      if (permission !== "granted") {
        showToast("Benachrichtigungen wurden nicht erlaubt.", true);
        return;
      }
      const keyRes = await api.get("/api/settings/push/vapid-key");
      const reg = await navigator.serviceWorker.ready;
      const sub = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(keyRes.public_key),
      });
      await api.post("/api/settings/push/subscribe", {
        endpoint: sub.endpoint,
        keys: sub.toJSON().keys,
        user_agent: navigator.userAgent,
      });
      showToast("Push aktiviert ✓");
    } catch (err) {
      showToast("Push-Aktivierung fehlgeschlagen. Zertifikat bestätigt?", true);
    }
  }

  async function testPush() {
    try {
      await api.post("/api/settings/push/test");
      showToast("Test-Push versendet ✓");
    } catch (err) {
      showToast("Test-Push fehlgeschlagen.", true);
    }
  }

  async function importChecklist(event) {
    event.preventDefault();
    const fileInput = event.target.elements.file;
    if (!fileInput.files.length) return;
    const fd = new FormData();
    fd.append("file", fileInput.files[0]);
    try {
      const res = await api.postForm("/api/settings/import-checklist", fd);
      showToast(`Import: ${res.created} neu, ${res.updated} aktualisiert ✓`);
      fileInput.value = "";
    } catch (err) {
      showToast(err.message, true);
    }
  }

  async function importBackup(event) {
    event.preventDefault();
    const fileInput = event.target.elements.file;
    if (!fileInput.files.length) return;
    if (!window.confirm("Backup importieren überschreibt ALLE aktuellen Daten! Fortfahren?")) return;
    const fd = new FormData();
    fd.append("file", fileInput.files[0]);
    try {
      const res = await api.postForm("/api/maintenance/backup/import", fd);
      showToast(`Backup importiert (${res.templates_restored} Vorlagen) ✓ – Seite wird neu geladen …`);
      setTimeout(() => window.location.reload(), 1500);
    } catch (err) {
      showToast(err.message, true);
    }
  }

  return (
    <>
      <h1>Einstellungen</h1>

      <section className="card">
        <h2>Grundstück &amp; E-Mail-Benachrichtigung</h2>
        <form className="form" onSubmit={(e) => { e.preventDefault(); save(); }}>
          <div className="grid2">
            <label>
              Name
              <input
                type="text"
                value={s.property.name}
                onChange={(e) => set("property", { ...s.property, name: e.target.value })}
              />
            </label>
            <label>
              Adresse
              <input
                type="text"
                value={s.property.address || ""}
                onChange={(e) => set("property", { ...s.property, address: e.target.value })}
              />
            </label>
          </div>

          <label className="check">
            <input
              type="checkbox"
              checked={s.channels.email}
              onChange={(e) => set("channels", { ...s.channels, email: e.target.checked })}
            />
            Tägliche Zusammenfassung per E-Mail aktiv
          </label>

          <div className="grid2">
            <label>
              SMTP-Server
              <input type="text" value={s.smtp.host} onChange={(e) => set("smtp", { ...s.smtp, host: e.target.value })} />
            </label>
            <label>
              Port
              <input
                type="number"
                min={1}
                max={65535}
                value={s.smtp.port}
                onChange={(e) => set("smtp", { ...s.smtp, port: e.target.value })}
              />
            </label>
          </div>
          <div className="grid2">
            <label>
              Verschlüsselung
              <select value={s.smtp.security} onChange={(e) => set("smtp", { ...s.smtp, security: e.target.value })}>
                <option value="starttls">STARTTLS</option>
                <option value="ssl">SSL/TLS</option>
                <option value="none">Keine</option>
              </select>
            </label>
            <label>
              Nutzer
              <input type="text" autoComplete="off" value={s.smtp.user} onChange={(e) => set("smtp", { ...s.smtp, user: e.target.value })} />
            </label>
          </div>
          <div className="grid2">
            <label>
              Passwort
              <input
                type="password"
                autoComplete="new-password"
                placeholder={s.smtp.password_set ? "gespeichert – leer lassen = unverändert" : ""}
                value={smtpPassword}
                onChange={(e) => setSmtpPassword(e.target.value)}
              />
            </label>
            <label>
              Absender
              <input type="text" value={s.smtp.from} onChange={(e) => set("smtp", { ...s.smtp, from: e.target.value })} />
            </label>
          </div>
          <div className="grid2">
            <label>
              Empfänger
              <input type="text" value={s.notify_email} onChange={(e) => set("notify_email", e.target.value)} />
            </label>
            <label>
              Tage im Voraus
              <input
                type="number"
                min={0}
                max={60}
                value={s.notify_days_ahead ?? 7}
                onChange={(e) => set("notify_days_ahead", e.target.value)}
              />
            </label>
          </div>

          <div className="form-actions">
            <button className="btn primary" type="submit" disabled={saving}>
              {saving ? "Speichern …" : "Speichern"}
            </button>
            <button className="btn" type="button" onClick={testEmail} disabled={saving}>
              Test-E-Mail senden
            </button>
          </div>
        </form>
      </section>

      <section className="card">
        <h2>Web Push (optional)</h2>
        {meta && meta.push_enabled ? (
          <>
            <p>
              Push-Kanal: <strong>{s.channels.push ? "aktiv" : "inaktiv"}</strong>. Voraussetzung:
              Das Zertifikat muss auf diesem Gerät bestätigt sein (siehe Hilfe).
            </p>
            <div className="form-actions">
              <button type="button" className="btn primary" onClick={subscribePush}>
                Push auf diesem Gerät aktivieren
              </button>
              <button type="button" className="btn" onClick={testPush}>
                Test-Push senden
              </button>
            </div>
          </>
        ) : (
          <p className="empty">
            Web Push ist deaktiviert (Umgebungsvariable HAUSMEISTER_PUSH_ENABLED=0). Aktivierung:
            README, Abschnitt „Web Push aktivieren".
          </p>
        )}
      </section>

      <section className="card">
        <h2>Backup</h2>
        <p>Backup-Verzeichnis: <code>{s.backup_dir}</code></p>
        <div className="form-actions">
          <a className="btn primary" href="/api/maintenance/backup/export">
            Backup jetzt herunterladen (ZIP)
          </a>
        </div>
        <form className="form" onSubmit={importBackup}>
          <label>
            Backup-Datei (ZIP) importieren
            <input type="file" accept=".zip" required />
          </label>
          <button className="btn danger" type="submit">Backup importieren (überschreibt Daten!)</button>
        </form>
        <p className="hint">
          Hinweis: Der geheime Schlüssel (.secret_key) ist nicht Teil des Backups. Nach einem
          Import auf fremdem System muss das SMTP-Passwort neu eingetragen werden. Für Schutz vor
          Container-Verlust: externes Ziel mounten – siehe README (NFS/CIFS).
        </p>
      </section>

      <section className="card">
        <h2>Aufgabenvorlagen importieren</h2>
        <p>
          CSV oder JSON mit den Spalten/Feldern laut README (Abschnitt „Checklisten-Import").
          Matching über den stabilen <code>slug</code> – bestehende Verläufe bleiben erhalten.
        </p>
        <form className="form" onSubmit={importChecklist}>
          <label>
            Datei (JSON oder CSV)
            <input type="file" name="file" accept=".json,.csv" required />
          </label>
          <button className="btn primary" type="submit">Importieren</button>
        </form>
        <p className="hint">
          Die mitgelieferten Vorlagen sind Platzhalter (Kennzeichnung „Platzhalter" in der
          Aufgabenliste) und vor dem ersten produktiven Einsatz durch echte Checklisten-Inhalte zu
          ersetzen.
        </p>
      </section>
    </>
  );
}

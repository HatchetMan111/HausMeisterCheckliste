import { api } from "../api.js";
import { useEffect, useState } from "react";

export default function CertificateHelp() {
  const [appUrl, setAppUrl] = useState("https://hausmeister.local");
  useEffect(() => {
    api.get("/api/meta").then((m) => m.app_url && setAppUrl(m.app_url)).catch(() => {});
  }, []);

  return (
    <>
      <h1>Zertifikat auf deinem Gerät bestätigen</h1>

      <section className="card">
        <p>
          Hausmeister läuft mit einem selbstsignierten Zertifikat für <code>{appUrl}</code>. Browser
          akzeptieren dieses Zertifikat nicht automatisch – jedes Gerät muss dem Zertifikat{" "}
          <strong>einmalig manuell vertrauen</strong>. Ohne diesen Schritt blockiert der Browser u.
          a. die Offline-Funktionen (Service Worker) und Web Push.
        </p>
        <p>
          Am einfachsten importierst du die lokale Stammzertifizierungsstelle (Root-CA):{" "}
          <a href="/certs/root-ca.crt">Root-CA herunterladen</a> (Datei{" "}
          <code>hausmeister-root-ca.crt</code>).
        </p>
        <p className="hint">
          Der erste Aufruf zeigt eine Browser-Warnung. Über „Erweitert → Weiter zu …" kannst du die
          Seite vorübergehend öffnen und dort die CA-Datei herunterladen. Danach folge den Schritten
          für dein Gerät.
        </p>
      </section>

      <section className="card">
        <h2>Android (Chrome)</h2>
        <ol>
          <li>Root-CA herunterladen (Link oben).</li>
          <li>Einstellungen → Sicherheit &amp; Datenschutz → Weitere Einstellungen → Verschlüsselung &amp; Anmeldedaten → Zertifikat installieren → CA-Zertifikat.</li>
          <li>Heruntergeladene Datei auswählen und installieren (Geräte-PIN bestätigen).</li>
          <li>Chrome vollständig schließen und erneut öffnen, dann <code>{appUrl}</code> aufrufen.</li>
        </ol>
      </section>

      <section className="card">
        <h2>iOS / iPadOS (Safari)</h2>
        <ol>
          <li>Root-CA in Safari herunterladen: es öffnet sich das Profil-Dialogfeld → „Heruntergeladenes Profil installieren" bestätigen.</li>
          <li>Einstellungen → Allgemein → VPN &amp; Device Management → Profil installieren.</li>
          <li>Wichtig: Einstellungen → Allgemein → Info → Zertifikatsvertrauenseinstellungen → für „hausmeister … Root-CA" den Schalter „Volles Vertrauen" aktivieren.</li>
          <li>Safari neu öffnen.</li>
        </ol>
      </section>

      <section className="card">
        <h2>Windows</h2>
        <ol>
          <li>Root-CA herunterladen.</li>
          <li>Doppelklick auf die Datei → „Zertifikat installieren" → Speicherort „Aktueller Benutzer" → „Alle Zertifikate in folgendem Speicher speichern" → „Vertrauenswürdige Stammzertifizierungsstellen".</li>
          <li>Browser neu starten.</li>
        </ol>
      </section>

      <section className="card">
        <h2>Linux (Desktop)</h2>
        <ol>
          <li>Root-CA herunterladen.</li>
          <li>Debian/Ubuntu: Datei nach <code>/usr/local/share/ca-certificates/hausmeister-root-ca.crt</code> kopieren (sudo), dann <code>sudo update-ca-certificates</code> ausführen.</li>
          <li>Fedora/RHEL: Datei nach <code>/etc/pki/ca-trust/source/anchors/</code> kopieren, dann <code>sudo update-ca-trust</code>.</li>
          <li>Browser neu starten.</li>
        </ol>
      </section>

      <section className="card">
        <h2>Prüfen, ob alles funktioniert</h2>
        <ol>
          <li><code>{appUrl}</code> ohne Warnung öffnen.</li>
          <li>Auf dieser Seite kein Hinweis mehr: die Offline-Funktionen (Service Worker) sind aktiv.</li>
          <li>Push testen: Einstellungen → Web Push → „Push auf diesem Gerät aktivieren".</li>
        </ol>
      </section>
    </>
  );
}

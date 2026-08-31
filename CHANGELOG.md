# Changelog

Alle nennenswerten Änderungen dieses Projekts werden hier dokumentiert.
Format orientiert an [Keep a Changelog](https://keepachangelog.com/), Versionierung
nach [SemVer](https://semver.org/).

## [0.2.0] - 2026-08-31

### Hinzugefügt

- **Jahres-Checkliste** (Seite „Jahresplan“) mit zwei Ansichten:
  📅 Monatsansicht (je Monat, umschaltbar) und 📋 Jahresübersicht (alle Monate
  auf einen Blick); Zähler für Aufgaben/erledigt/offen; Filter ⚡ Wichtig,
  ⏱ Empfohlen, 📌 Optional und 💡 Smart-Tipps; je Monat „✓ Alle abhaken“ und
  „↺ Zurücksetzen“ (Rückgängig inkl. Verlaufsbereinigung des Monats)
- Neue REST-Endpunkte: `POST /api/maintenance/complete-month/{monat}` und
  `POST /api/maintenance/reopen-month/{monat}` (mit Validierung 1–12)
- Fertige Jahresbibliothek `data/templates/jahresplan.json`: **158 Aufgaben**,
  monatsgenau über das Jahr (Heizung & Energie, PV, Dach/Fassade/Keller,
  Sicherheit inkl. 30 neutral formulierter Smart-Home-/Sensorik-Tipps,
  Wasser & Pool, Garten mit Schnittregel-Hinweisen, Fenster & Türen);
  170 Fälligkeiten pro Jahr
- Installer lädt bei leerer Datenbank jetzt die Jahresplan-Bibliothek;
  `checklist.json` bleibt als Formatbeispiel für eigene Importe

### Geändert

- README: neue Kapitel „Jahres-Checkliste nutzen“ und überarbeitete
  Funktionsliste; Nutzungshinweise auf die Jahresbibliothek angepasst

## [0.1.12] - 2026-08-31

### Geändert

- Dashboard ist jetzt **auch über HTTP** erreichbar – ohne jeden
  Zertifikatsaufwand: `http://hausmeister.local` und `http://<Container-IP>`
  (Port 80) sofort nutzbar. HTTPS bleibt parallel aktiv und ist nur noch für
  die PWA-Extras nötig (App-Installation, Offline-„Erledigt“-Klicks, Web Push),
  da Browser dafür einen „secure context“ verlangen
- Installer-Verifikation: HTTP-Health-Check ist maßgeblich; HTTPS-Fehler
  führen nur noch zu einem Hinweis statt eines Abbruchs
- Abschluss-Zusammenfassung zeigt beide Wege (HTTP sofort / HTTPS für PWA)
- README: „Erste Schritte“ und Zertifikats-Abschnitt entsprechend angepasst

## [0.1.11] - 2026-08-31

### Behoben

- Caddy startete mit der frisch geschriebenen Konfiguration nicht: In
  Bash-Heredocs bleibt `\t` ein literales Backslash-t, die generierte
  Caddyfile enthielt damit ungültige Direktiven (`\tadmin off` …) – der Fehler
  war bisher nie aufgefallen, weil die Datei durch den Paket-Default nie
  tatsächlich geschrieben wurde. Jetzt: saubere Einrückung per Leerzeichen,
  Caddyfile wird vor dem Start per `caddy validate` (als Caddy-Benutzer,
  damit der Storage korrekt gehört wird) geprüft, Storage-Besitzrechte
  abgesichert

## [0.1.10] - 2026-08-31

### Behoben

- Kernursache der fehlgeschlagenen Health-Checks: Das Debian-Caddy-Paket legt
  eine eigene Standard-Caddyfile an (Demo-Site `localhost`). Der Installer
  schrieb seine Konfiguration nur, wenn die Datei noch nicht existierte – Caddy
  lief dadurch mit der Demo-Konfiguration: aktiv, aber ohne
  `hausmeister.local`-Site, ohne interne CA und ohne Port 443. Jetzt wird die
  Hausmeister-Caddyfile immer gesetzt (vorhandene Fremd-Konfiguration wird
  gesichert, marker-basiert), Caddy zur Übernahme neu gestartet
- Eigene `caddy.service` wird nur noch installiert, wenn das Paket keine
  mitbringt; die mitgelieferte Unit enthält jetzt
  `AmbientCapabilities=CAP_NET_BIND_SERVICE`

## [0.1.9] - 2026-08-31

### Behoben

- Health-Check der Container-Installation schlug fehl, obwohl App und Caddy
  liefen: (1) `libnss-mdns` fehlte, damit ließ sich `hausmeister.local` im
  Container nicht per mDNS auflösen; (2) die Root-CA wurde nie erzeugt, weil
  der Auslöse-Handshake SNI `127.0.0.1` statt `hausmeister.local` sendete
  (Caddy stellt keine Zertifikate für unbekannte SNI aus). Jetzt: `libnss-mdns`
  wird installiert, Zertifikats-Ausstellung wird mit korrektem SNI angestoßen,
  Root-CA wird exportiert und container-intern vertraut; Health-Check prüft
  mDNS zuerst, danach lokale Auflösung, bei Fehlern mit Diagnose-Hinweis

## [0.1.8] - 2026-08-31

### Behoben

- Container-Installer brach mit „sudo: command not found“ ab: Debian-LXCs
  bringen kein `sudo` mit. Die Befehle als Anwendungsbenutzer (Alembic,
  Aufgaben-Import) nutzen jetzt `runuser` aus util-linux (immer vorhanden);
  `update.sh` analog korrigiert
- Locale-Warnungen („perl: warning: Falling back …“) im Container-Installer
  durch gesetztes `LC_ALL=C.UTF-8` beseitigt

## [0.1.7] - 2026-08-31

### Behoben

- Vorlagen-Download und Root-Disk nutzten denselben Storage: Auf Standard-Proxmox
  kann das LVM-thin-Storage (`local-lvm`) keine Container-Vorlagen speichern
  („storage 'local-lvm' does not support templates“). Der Vorlagen-Storage wird
  jetzt separat und automatisch ermittelt (erster Storage mit Content
  `vztmpl`), ist per `HAUSMEISTER_TEMPLATE_STORAGE` überschreibbar, und der
  Prompt für die Root-Disk ist klar als „Container-Festplatte“ beschriftet

## [0.1.6] - 2026-08-31

### Behoben

- Container-Erstellung schlug mit „VM … already exists“ fehl, wenn die
  vorgeschlagene ID durch eine bestehende VM belegt war (`pct list` sieht nur
  Container, VMIDs sind aber clusterweit für VMs und CTs gemeinsam vergeben).
  Die freie ID wird jetzt per `pvesh get /cluster/nextid` ermittelt
  (wie bei den Community-Skripten üblich); Fallback prüft `pct list` **und**
  `qm list`

## [0.1.5] - 2026-08-31

### Behoben

- Installation hing reproduzierbar an der ersten Eingabe in ein Readline-Prompt
  (`read -e -i`): in PVE-Web-Konsole (noVNC) und einzelnen SSH-Clients kollidiert
  der readline-Raw-Modus mit eingefügtem Text, sodass `read` endlos wartete.
  Alle Prompts nutzen jetzt schlichtes `read -r` (Vorgabe weiterhin in Klammern,
  Enter = übernehmen) – robust in jedem Terminal, ohne Funktionsverlust

## [0.1.4] - 2026-08-31

### Behoben

- Vorlagen-Erkennung brach unter `pipefail` ab, sobald `pveam` keine
  Debian-13-Vorlage lieferte (z. B. ältere Proxmox-Versionen): der Skript-Abbruch
  geschah direkt nach „Vorlage herunterladen“, der Debian-12-Fallback war nie
  erreichbar. Jetzt: `grep` nicht-abortierend, Fallback auf Debian-12 mit
  Hinweis, klare Fehlermeldung mit Prüfhinweis (`pveam available`), falls gar
  keine Standardvorlage existiert, und explizite Fehlermeldung bei
  fehlgeschlagenem Vorlagen-Download
- Container-IP-Ermittlung am Ende ist fehlertolerant (kein Abbruch mehr nach
  erfolgreicher Installation, falls `hostname -I` im Container scheitert)

## [0.1.3] - 2026-08-31

### Behoben

- Host-Skript brach unter `set -u` mit „HAUSMEISTER_NET_MODE: unbound variable“
  ab, wenn die Umgebungsvariable nicht gesetzt war (reguläre interaktive
  Installation im Einzeiler betroffen)

## [0.1.2] - 2026-08-31

### Hinzugefügt

- Einzeiler-Installation im Stil der Proxmox-Community-Skripte:
  `bash -c "$(curl -fsSL https://raw.githubusercontent.com/HatchetMan111/HausMeisterCheckliste/main/hausmeister.sh)"`
  – lädt das Repository, erstellt den Container, installiert die Anwendung und
  gibt am Ende die Dashboard-Adressen aus (hausmeister.local und Container-IP)
- Auto-Modus für das Host-Skript (`ct/hausmeister.sh --auto` bzw.
  `HAUSMEISTER_AUTO=1`) mit Standardeinstellungen (DHCP, automatisch ermittelter
  Storage); Netzwerk optionally per `HAUSMEISTER_NET_MODE`/`HAUSMEISTER_CT_IP`/
  `HAUSMEISTER_CT_GW` vorgeben
- Abschluss-Zusammenfassung zeigt nun ausdrücklich beide Dashboard-Adressen
  (mDNS-Name bevorzugt, IP als Alternative mit Zertifikatshinweis)

## [0.1.1] - 2026-08-31

### Geändert

- Installer (`ct/hausmeister.sh`, `install/hausmeister-install.sh`) nutzen jetzt
  standardmäßig `https://github.com/HatchetMan111/HausMeisterCheckliste.git` –
  `bash install/hausmeister-install.sh` funktioniert damit ohne Umgebungsvariable;
  im Host-Skript ist die URL als Vorgabe vorbelegt (Enter = übernehmen)
- README erweitert: Einführung „Was ist das – und wofür?“, Alltagsnutzung,
  konkrete Installationsbefehle mit echter Repository-URL, Tabelle der
  Installer-Umgebungsvariablen und Checkliste „Erste Schritte nach der
  Installation“

## [0.1.0] - 2026-08-31

### Hinzugefügt

- Kalenderbasierte Wartungsplanung mit vier eindeutigen Zeitplan-Typen:
  `one_time`, `interval_days`, `annual_window` (Jahresfenster) und
  `annual_repeat` (eigene Fälligkeit je Monat)
- Aufgabenbibliothek mit Bereichen (Haus, Hof, Technik, Garten, Sicherheit),
  Kategorien, Prioritäten; Aufgaben anlegen/bearbeiten/deaktivieren/löschen
- Dashboard mit Überfällig / Heute / Diese Woche / Demnächst, Verlauf aller
  Erledigungen (inkl. Notiz und Person)
- PWA: Service-Worker-Cache für die UI-Shell, IndexedDB-Schreib-Queue mit
  Background Sync für Offline-„Erledigt“-Klicks, Web-App-Manifest und Icons
- REST-API: Aufgaben, Wartungs-Fälligkeiten, Verlauf, Einstellungen, Backup,
  Push-Abonnements; Mängel-Endpunkte als vorbereitete 501-Stubs (V2)
- SQLite mit versionierten Alembic-Migrationen; Schema enthält vorbereitete,
  im MVP inaktive Tabellen: `defects`, `attachments`, `users`, `sessions`
  (Passwort-Hash, Rollen), `push_subscriptions`, `notification_settings`,
  `properties` (im MVP genau ein Datensatz)
- TLS via Caddy mit `tls internal` auf dem mDNS-Namen `hausmeister.local`
  (Avahi) – Zertifikat hängt am Namen, nicht an der DHCP-IP; Root-CA wird
  unter `/certs/root-ca.crt` bereitgestellt und container-intern vertraut
- Web Push als Feature-Flag (`HAUSMEISTER_PUSH_ENABLED`) inkl. automatischer
  VAPID-Schlüsselerzeugung
- E-Mail-/SMTP-Zusammenfassung als primärer Benachrichtigungsweg; Zugangsdaten
  werden in der Web-UI hinterlegt und verschlüsselt gespeichert (Fernet,
  Schlüssel in `data/.secret_key`)
- Backup: ZIP-Export über die Web-UI, tägliche DB-Sicherung per systemd-Timer,
  konfigurierbares `HAUSMEISTER_BACKUP_DIR` (u. a. für NFS/CIFS-Mounts),
  Backup-Import über die Web-UI
- Systemd-Setup: `hausmeister.service`, `hausmeister-daily.timer` +
  `hausmeister-daily.service` (ruft `python -m app.services.scheduler --run-daily`
  auf – bewusst kein In-Process-Scheduler), `caddy.service`
- Installer zweistufig: `ct/hausmeister.sh` (Host: interaktive Netzwerk-/Storage-
  Abfrage, unprivilegierter Debian-13-LXC mit `onboot=1`) +
  `install/hausmeister-install.sh` (Container: idempotent, vollständige
  Fehlerdiagnostik, Verifikation aller Dienste inkl. Timer und Health-Check)
- `update.sh`: tag-basiertes Update mit Vorab-Backup, Migrationen und Verifikation
- Platzhalter-Aufgabenbibliothek (`data/templates/checklist.json`,
  `source: placeholder`) mit 34 Aufgaben über alle Bereiche
- `scripts/import_checklist.py`: JSON-/CSV-Import mit Upsert über den stabilen
  `slug` – Reimporte ändern keine bestehenden `task_instances`/`task_completions`
- Tests (Rekurrenzlogik, Aufgaben-API inkl. Import, REST-Flows inkl.
  Backup-Import, Einstellungen mit verschlüsseltem Passwort) und CI-Workflow
  (pytest, Alembic up/down/up, `bash -n`, ShellCheck)
- Anleitung „Zertifikat auf deinem Gerät bestätigen“ (README + in der App unter
  /help/certificate) für Android, iOS, Windows und Linux

### Bekannte Einschränkungen

- Die mitgelieferte Aufgabenbibliothek ist ein ausdrücklich gekennzeichneter
  Platzhalter und vor dem ersten produktiven Einsatz durch echte Checklisten-
  Inhalte zu ersetzen (Import-Tool, Matching über `slug`)
- Kein Login im MVP (Schema vorbereitet); Zugriff für LAN/VPN vorgesehen
- Web Push ohne bestätigtes Geräte-Zertifikat nicht nutzbar (dokumentiert)
- Kein sensordatenbasiertes/prädiktives Modell in dieser Version

# Changelog

Alle nennenswerten Änderungen dieses Projekts werden hier dokumentiert.
Format orientiert an [Keep a Changelog](https://keepachangelog.com/), Versionierung
nach [SemVer](https://semver.org/).

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

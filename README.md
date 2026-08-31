# Hausmeister

Lokaler, kalenderbasierter Wartungs- und Aufgabenplaner für Haus & Hof.
Präventive Planung statt Sensorik: Aufgaben nach Monatsfenstern, festen Monaten,
Tages-Intervallen oder Einzelterminen – inkl. Verlauf, Offline-Fähigkeit,
Backup und E-Mail-Zusammenfassung.

- **Vollständig lokal:** läuft in einem unprivilegierten LXC-Container, keine Cloud-Abhängigkeit.
- **PWA + REST-API:** installierbare Web-App mit Offline-Schreib-Queue („Erledigt“-Klicks ohne Netz werden nachgeholt).
- **Kein Login im MVP:** Zugriff ist für LAN/VPN gedacht. Tabellen für Benutzer, Sitzungen und Rollen liegen bereits im Schema (inaktiv).

---

## Inhalt

1. [Funktionsumfang](#funktionsumfang)
2. [Architektur](#architektur)
3. [Installation](#installation)
4. [Zertifikat auf deinem Gerät bestätigen (Pflichtschritt)](#zertifikat-auf-deinem-gerät-bestätigen-pflichtschritt)
5. [Web Push aktivieren](#web-push-aktivieren)
6. [E-Mail-Benachrichtigung (SMTP)](#e-mail-benachrichtigung-smtp)
7. [Backup & Wiederherstellung](#backup--wiederherstellung)
8. [Checklisten-Import](#checklisten-import)
9. [Update](#update)
10. [Zeitplan-Typen](#zeitplan-typen)
11. [Entwicklung & Tests](#entwicklung--tests)
12. [Scope](#scope)

---

## Funktionsumfang

- Aufgabenbibliothek mit Bereichen (Haus, Hof, Technik, Garten, Sicherheit) und Kategorien
- Aufgaben aktivieren/deaktivieren, eigene Aufgaben anlegen, bearbeiten, löschen
- Vier eindeutige Zeitplan-Typen (siehe [Zeitplan-Typen](#zeitplan-typen))
- Dashboard: **Überfällig / Heute / Diese Woche / Demnächst**
- Verlauf aller Erledigungen (wann, wer, Notiz)
- Offline-Modus: UI-Shell wird gecacht, „Erledigt“-Klicks landen in einer IndexedDB-Queue
  und werden per Background Sync nachgeholt
- Backup als ZIP-Download, Backup-Ziel konfigurierbar, tägliche DB-Sicherung per Timer
- E-Mail-Zusammenfassung als primärer Benachrichtigungsweg; Web Push optional
- Mitgelieferte Platzhalter-Aufgabenbibliothek (vor dem Produktionseinsatz ersetzen!)

## Architektur

| Komponente | Wahl |
|---|---|
| Backend | Python + FastAPI |
| Frontend | Server-seitiges HTML (Jinja2) + PWA (Service Worker, Manifest) |
| Datenbank | SQLite + versionierte Alembic-Migrationen |
| Webserver | Uvicorn (intern :8080) hinter Caddy (extern :443, TLS-Terminierung) |
| Dienste | systemd: `hausmeister.service`, `hausmeister-daily.timer`, `caddy.service` |
| Erreichbarkeit | fester mDNS-Name `hausmeister.local` (Avahi) – unabhängig von DHCP-IPs |
| Container | Debian 13, unprivilegiert, 2 vCPU, 2 GB RAM, 8 GB Disk, `onboot=1` |

Wichtige Design-Entscheidungen:

- **TLS ist Pflicht**, kein Nice-to-have: Service Worker und Web Push brauchen einen
  „secure context“. Das selbstsignierte Zertifikat hängt am **mDNS-Namen**
  (`hausmeister.local`), nicht an der IP – damit überlebt es DHCP-Wechselspiele.
- **Kein In-Process-Scheduler:** der tägliche Lauf (Instanzen erzeugen, Backup,
  E-Mail-Zusammenfassung) läuft als **systemd-Timer** über den CLI-Befehl
  `python -m app.services.scheduler --run-daily` – überlebt App-Neustarts sauber und
  ist mit `systemctl status hausmeister-daily.timer` prüfbar.
- **Tag-basierte Installation & Updates:** Erstinstall und `update.sh` arbeiten gegen
  Git-Tags/Releases, nie blind gegen einen Entwicklungs-Branch.

## Installation

Zwei Stufen:

### 1. Auf dem Proxmox-Host: `ct/hausmeister.sh`

Fragt interaktiv ab (DHCP ist Standard und unproblematisch, da das Zertifikat am
mDNS-Namen hängt):

- Container-Hostname (Standard: `hausmeister`)
- Netzwerk-Bridge (Standard: `vmbr0`)
- IP-Vergabe: **dhcp** oder **statisch** (bei statisch: IP/CIDR + Gateway)
- Storage für die Root-Disk
- Git-Repository-URL und Version/Tag (`latest` = höchster Release-Tag)
- Container-ID

Danach: Vorlage herunterladen, unprivilegierten Container erstellen
(`onboot=1`, 2 vCPU, 2 GB RAM, 8 GB), starten und den Installer im Container ausführen.

Alternativ direkt im existierenden Container:

```bash
HAUSMEISTER_REPO_URL=<git-url> bash install/hausmeister-install.sh
```

### 2. Im Container: `install/hausmeister-install.sh`

Macht (idempotent, mit vollständiger Fehlerdiagnostik und Log unter
`/var/log/hausmeister-install-*.log`):

1. Basispakete (Python, Git, Avahi/mDNS, Caddy, …), Zeitzone setzen
2. Systembenutzer anlegen, Repository **tag-basiert** nach `/opt/hausmeister` laden
3. Virtualenv + Abhängigkeiten, Alembic-Migrationen anwenden
4. Platzhalter-Aufgabenbibliothek importieren (nur wenn Datenbank leer ist)
5. `.env` (inkl. `HAUSMEISTER_PUSH_ENABLED`, `HAUSMEISTER_APP_URL`, `HAUSMEISTER_BACKUP_DIR`)
6. systemd-Units + Caddyfile (`tls internal` auf `hausmeister.local`)
7. Dienste starten, Root-CA exportieren, **Verifikation**: `systemctl is-active`
   (App, Caddy, Timer), Health-Check über `https://hausmeister.local/health`
8. Zusammenfassung mit Container-IP, finaler URL und Hinweis auf den
   Zertifikats-Bestätigungsschritt

## Zertifikat auf deinem Gerät bestätigen (Pflichtschritt)

Hausmeister nutzt ein selbstsigniertes Zertifikat für `hausmeister.local`.
Browser akzeptieren es **nicht automatisch** – jedes Gerät (Handy, Tablet, Laptop)
muss dem Zertifikat **einmalig manuell vertrauen**. Ohne diesen Schritt blockiert der
Browser die Service-Worker-Registrierung (Offline-Modus) und Web Push bleibt unbenutzbar.

Die Web-App liefert unter **`https://hausmeister.local/certs/root-ca.crt`** die lokale
Stammzertifizierungsstelle aus; dieselbe Anleitung ist in der App unter
**Hilfe → Zertifikat bestätigen** verlinkt.

Erster Aufruf (jedes Gerät):

1. `https://hausmeister.local` öffnen – der Browser zeigt eine Warnung.
2. Über *Erweitert → Weiter zu hausmeister.local (unsicher)* die Seite vorübergehend öffnen.
3. Root-CA laden: `https://hausmeister.local/certs/root-ca.crt`
4. Unten das passende Verfahren für dein Gerät ausführen.
5. Browser schließen, neu öffnen, Seite erneut aufrufen – keine Warnung mehr.

### Android (Chrome)

1. Root-CA-Datei herunterladen.
2. *Einstellungen → Sicherheit & Datenschutz → Weitere Einstellungen →
   Verschlüsselung & Anmeldedaten → Zertifikat installieren → CA-Zertifikat.*
3. Datei auswählen, Gerätesperre bestätigen.
4. Chrome vollständig beenden und neu starten.

### iOS / iPadOS (Safari)

1. Root-CA in Safari herunterladen → *Heruntergeladenes Profil installieren*.
2. *Einstellungen → Allgemein → VPN & Device Management → Profil installieren.*
3. **Zusätzlich nötig (iOS):** *Einstellungen → Allgemein → Info →
   Zertifikatsvertrauenseinstellungen* → für die installierte Root-CA
   „Volles Vertrauen“ aktivieren.
4. Safari neu öffnen.

### Windows

1. Root-CA-Datei doppelklicken → *Zertifikat installieren*.
2. Speicherort „Aktueller Benutzer“, dann *Alle Zertifikate in folgendem Speicher
   speichern → Vertrauenswürdige Stammzertifizierungsstellen*.
3. Browser neu starten.

### Linux (Desktop)

```bash
# Debian/Ubuntu
sudo cp hausmeister-root-ca.crt /usr/local/share/ca-certificates/
sudo update-ca-certificates
# Fedora/RHEL
sudo cp hausmeister-root-ca.crt /etc/pki/ca-trust/source/anchors/
sudo update-ca-trust
```

Danach den Browser neu starten. Prüfung: Seite ohne Warnung, unter
*Einstellungen → Web Push* lässt sich Push registrieren.

## Web Push aktivieren

Web Push ist ein **Feature-Flag** und standardmäßig aus:

```bash
# in /opt/hausmeister/.env
HAUSMEISTER_PUSH_ENABLED=1
systemctl restart hausmeister
```

Voraussetzungen: funktionierendes TLS und das bestätigte Zertifikat auf dem Gerät
(siehe oben). Danach in der Web-UI unter *Einstellungen → Web Push* das Gerät
anmelden. VAPID-Schlüssel werden beim ersten Aufruf automatisch erzeugt und in der
Datenbank abgelegt. Push-Abonnements liegen in der Tabelle `push_subscriptions`.

## E-Mail-Benachrichtigung (SMTP)

Zugangsdaten werden **nicht** im Installer abgefragt, sondern nach der Installation
in der Web-UI eingetragen (*Einstellungen → E-Mail-Benachrichtigung*) und in der
SQLite-Tabelle `settings` gespeichert – das Passwort **verschlüsselt**, niemals im
Klartext. Der Schlüssel dafür liegt in `data/.secret_key` (chmod 600, bei Installation
erzeugt). Sobald Host, Empfänger gesetzt und der Kanal aktiv sind, verschickt der
tägliche Timer eine Zusammenfassung aller fälligen/überfälligen Aufgaben.
Ein Test-Versand ist per Knopfdruck möglich.

## Backup & Wiederherstellung

- **Download:** *Einstellungen → Backup → Backup jetzt herunterladen (ZIP)* bzw.
  `GET /api/maintenance/backup/export`. Enthält die Datenbank und die Vorlagen.
- **Täglich:** der Timer sichert die DB nach `HAUSMEISTER_BACKUP_DIR`
  (Standard `data/backups`, Aufbewahrung: 14 Dateien, konfigurierbar über
  `HAUSMEISTER_BACKUP_KEEP`).
- **Import:** *Einstellungen → Backup importieren* überschreibt die Datenbank.
  Achtung: `data/.secret_key` ist **nicht** Teil des Backups. Auf einem fremden System
  muss das SMTP-Passwort nach dem Import neu eingetragen werden (der restliche Betrieb
  ist nicht betroffen).

**Container-Totalausfall absichern:** Standard-Backup-Ziel liegt im Container. Für
echte Redundanz ein externes Ziel mounten und `HAUSMEISTER_BACKUP_DIR` darauf setzen,
z. B. NFS oder CIFS:

```bash
# /etc/fstab im Container (Beispiel NFS)
nas.fritz.box:/volume1/backups  /mnt/backups  nfs  defaults,_netdev  0  0
# /etc/fstab im Container (Beispiel CIFS)
//nas.fritz.box/backups  /mnt/backups  cifs  credentials=/root/.smbcred,_netdev  0  0

# /opt/hausmeister/.env
HAUSMEISTER_BACKUP_DIR=/mnt/backups/hausmeister
systemctl restart hausmeister
```

Alternativ den ZIP-Download regelmäßig manuell/extern abholen.

## Checklisten-Import

Die mitgelieferte Bibliothek (`data/templates/checklist.json`) ist ein **Platzhalter**
(`"source": "placeholder"`, in der Aufgabenliste als „Platzhalter“ markiert) auf Basis
allgemein anerkannter Wartungsempfehlungen. **Vor dem ersten produktiven Einsatz** durch
die eigenen Checklisten ersetzen:

```bash
/opt/hausmeister/venv/bin/python /opt/hausmeister/scripts/import_checklist.py checkliste.json
/opt/hausmeister/venv/bin/python /opt/hausmeister/scripts/import_checklist.py checkliste.csv --deactivate-missing
```

Auch über die Web-UI möglich (*Einstellungen → Aufgabenvorlagen importieren*).

Matching erfolgt über den **stabilen `slug`**, nicht über den Titel: existiert der Slug,
wird die Aufgabe aktualisiert statt dupliziert – bestehende Fälligkeiten
(`task_instances`) und Verlaufseinträge (`task_completions`) bleiben beim Reimport
erhalten.

### JSON-Format

```json
{
  "version": 1,
  "source": "meine-quelle",
  "areas": [{ "slug": "haus", "name": "Haus" }],
  "categories": [{ "slug": "heizung", "name": "Heizung", "area": "technik" }],
  "tasks": [
    {
      "slug": "lueftungsfilter-wechseln",
      "title": "Filter der Lüftungsanlage wechseln",
      "description": "Aussen- und Innenfilter wechseln.",
      "area": "technik",
      "category": "heizung",
      "priority": "high",
      "schedule_type": "annual_repeat",
      "repeat_months": [1, 4, 7, 10],
      "estimated_minutes": 30,
      "source": "meine-quelle"
    }
  ]
}
```

### CSV-Format

Header-Zeile mit den Spalten: `slug,title,description,area,category,priority,
schedule_type,interval_days,window_start_month,window_end_month,repeat_months,
repeat_day,due_date,start_date,estimated_minutes,source`.
`repeat_months` als `3;6;9;12`. Pflichtspalten: `slug`, `title`.

## Update

```bash
bash update.sh   # im Container, als root
```

Sichert vorher die Datenbank, wechselt auf den **höchsten Git-Tag**, installiert
ggf. neue Abhängigkeiten, fährt Alembic-Migrationen hoch, startet den Dienst neu
und verifiziert den Health-Check. Läuft bereits der höchste Tag, geschieht nichts.

## Zeitplan-Typen

| Typ | Bedeutung | Felder |
|---|---|---|
| `one_time` | einmalige Aufgabe mit festem Datum | `due_date` |
| `interval_days` | wiederkehrend im festen Tages-Abstand, kalenderunabhängig (z. B. alle 90 Tage) | `interval_days`, optional `start_date` als Anker |
| `annual_window` | fällt **einmal pro Jahr** an; fällig ab Fensterbeginn, überfällig nach Fensterende – Erledigung irgendwann im Fenster zählt | `window_start_month`, `window_end_month` (1–12; Start > Ende = Fenster über Jahreswechsel) |
| `annual_repeat` | erscheint **separat in jedem** gelisteten Monat als eigene Fälligkeit (z. B. Filterwechsel alle drei Monate) | `repeat_months` (Liste 1–12), optional `repeat_day` |

Nach dem Erledigen einer `interval_days`-Aufgabe wird die nächste Fälligkeit sofort
angeplegt (Letzte-Erledigung + Intervall); die übrigen Typen erzeugen neue Instanzen
über den täglichen Timer bzw. `ensure-instances`.

## Entwicklung & Tests

```bash
python3 -m venv venv && venv/bin/pip install -r requirements.txt -r requirements-dev.txt
venv/bin/alembic upgrade head                                   # Schema
HAUSMEISTER_DATA_DIR=/tmp/hm venv/bin/python scripts/import_checklist.py data/templates/checklist.json
venv/bin/uvicorn app.main:app --port 8080                       # Dev-Server
venv/bin/pytest                                                 # Tests
```

CI (`.github/workflows/ci.yml`): pytest, Alembic up/down/up, `bash -n` und
ShellCheck für alle Shell-Skripte.

Dienste im Betrieb:

```bash
systemctl status hausmeister              # Web-App
systemctl status caddy                    # Reverse-Proxy/TLS
systemctl status hausmeister-daily.timer  # täglicher Lauf
journalctl -u hausmeister-daily.service   # Log des täglichen Laufs
```

## Scope

**Im MVP:** alles oben Genannte. Eine Installation entspricht **einem Grundstück**
(Haus, Hof, Technik als Bereiche darunter); die `properties`-Tabelle existiert im
Schema, ist aber auf einen Datensatz beschränkt – echtes Multi-Property ist V2.

**V2 (bewusst verschoben):** geführter Wartungsrundgang, Mängelverwaltung mit
Foto-Upload (Tabellen `defects`/`attachments` liegen vorbereitet im Schema, API
antwortet mit 501), Mehrbenutzer/Rollen (Tabellen `users`/`sessions` vorbereitet,
inaktiv), Statistik-Ansichten, sensordatenbasierte/prädiktive Erweiterungen.

## Lizenz

MIT – siehe [LICENSE](LICENSE).

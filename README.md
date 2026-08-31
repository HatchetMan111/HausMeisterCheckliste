# Hausmeister

Lokaler, kalenderbasierter Wartungs- und Aufgabenplaner für Haus & Hof.
Präventive Planung statt Sensorik: Aufgaben nach Monatsfenstern, festen Monaten,
Tages-Intervallen oder Einzelterminen – inkl. Verlauf, Offline-Fähigkeit,
Backup und E-Mail-Zusammenfassung.

## Was ist das – und wofür?

Jedes Haus hat wiederkehrende Pflichtaufgaben, die leicht vergessen werden:
Dachrinne im Herbst leeren, Rauchmelder vierteljährlich testen, Lüftungsfilter
alle drei Monate wechseln, Bewässerung vor dem ersten Frost winterfest machen.
Zettel, Merkhäfte und Tabellen versagen genau dann, wenn der Alltag dazwischenkommt –
und niemand weiß mehr, wann der Feuerlöscher zuletzt geprüft wurde.

Hausmeister nimmt dir das Merken ab:

- **Du legst einmal fest, wann was fällig ist** – als Jahresfenster („Dachrinne:
  Oktober–November“), feste Monate („Rauchmelder: Jan/Apr/Jul/Okt“),
  Tages-Intervall („Feuerlöscher-Fachwartung: alle 730 Tage“) oder Einzeltermin.
- **Hausmeister plant daraus selbstständig Fälligkeiten**, zeigt sie auf einem
  Dashboard (Überfällig / Heute / Diese Woche / Demnächst) und schickt dir auf
  Wunsch täglich eine E-Mail-Zusammenfassung.
- **Ein Klick auf „Erledigt“** dokumentiert, wann und von wem die Aufgabe gemacht
  wurde – der Verlauf zeigt auf einen Blick die Historie jeder Aufgabe.
- **Auch im Keller, Garten oder auf dem Dach ohne Empfang nutzbar:** die App ist
  eine PWA – auf dem Handy wie eine eigene App installierbar, „Erledigt“-Klicks
  ohne Netz werden automatisch nachgeholt.
- **Alles läuft bei dir zu Hause** – in einem kleinen Container auf dem eigenen
  Server, ohne Cloud, ohne Konto, ohne Abhängigkeit von einem Anbieter. Die Daten
  gehören dir; Backups sind ein ZIP-Download.

Gedacht für Eigentümerinnen und Eigentümer von Haus, Hof und Garten, für
Zweitwohnungen oder kleine Gewerbeimmobilien – für alle, die Wartung vorab planen
statt hinterher reparieren. Sensordaten, Energiemanager oder „predictive
maintenance“ sind bewusst **nicht** Teil dieser Version.

- **Vollständig lokal:** läuft in einem unprivilegierten LXC-Container, keine Cloud-Abhängigkeit.
- **PWA + REST-API:** installierbare Web-App mit Offline-Schreib-Queue („Erledigt“-Klicks ohne Netz werden nachgeholt).
- **Kein Login im MVP:** Zugriff ist für LAN/VPN gedacht. Tabellen für Benutzer, Sitzungen und Rollen liegen bereits im Schema (inaktiv).

---

## Inhalt

1. [Funktionsumfang](#funktionsumfang)
2. [So nutzt du Hausmeister im Alltag](#so-nutzt-du-hausmeister-im-alltag)
3. [Architektur](#architektur)
4. [Installation](#installation)
5. [Erste Schritte nach der Installation](#erste-schritte-nach-der-installation)
6. [Zertifikat auf deinem Gerät bestätigen (nur für Offline-Modus & Push)](#zertifikat-auf-deinem-gerät-bestätigen-nur-für-offline-modus--push)
7. [Web Push aktivieren](#web-push-aktivieren)
8. [E-Mail-Benachrichtigung (SMTP)](#e-mail-benachrichtigung-smtp)
9. [Backup & Wiederherstellung](#backup--wiederherstellung)
10. [Checklisten-Import](#checklisten-import)
11. [Update](#update)
12. [Zeitplan-Typen](#zeitplan-typen)
13. [Entwicklung & Tests](#entwicklung--tests)
14. [Scope](#scope)

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

## So nutzt du Hausmeister im Alltag

**Typischer Ablauf:**

1. **Aufgaben einmal festlegen.** Beim ersten Start ist eine vorgefertigte
   Bibliothek mit 34 gängigen Wartungsaufgaben geladen (Platzhalter – siehe
   [Checklisten-Import](#checklisten-import)). Du übernimmst sie, passt sie an
   oder importierst deine eigene Liste. Eigene Aufgaben legst du unter
   *Aufgaben → + Neue Aufgabe* an: Titel, Bereich, Zeitplan-Typ, fertig.
2. **Hausmeister rechnet.** Aus jedem Zeitplan entsteht automatisch eine konkrete
   Fälligkeit – z. B. erscheint „Dachrinnen reinigen“ ab 1. Oktober im Dashboard
   und gilt nach Ende November als überfällig, falls unerledigt.
3. **Morgens überblicken.** Dashboard öffnen (am Handy oder PC): Was ist
   überfällig, was ist heute dran, was kommt diese Woche? Per E-Mail erhältst du
   dieselbe Übersicht täglich um 7:30 Uhr.
4. **Erledigen und abhaken.** Knopf „Erledigt“ – fertig. Optional mit Notiz
   („neue Dichtung eingesetzt“), Verlauf dokumentiert automatisch Datum und Person.
   Eine Aufgabe, die in diesem Jahr entfällt (z. B. Heckenschnitt wegen Vogelnest),
   überspringst du per „Überspringen“ – sie bleibt dokumentiert und kehrt nächstes
   Jahr wieder.
5. **Unterwegs offline.** Handy in den Keller oder auf die Leiter, kein WLAN:
   Die App startet trotzdem (Installierte PWA). „Erledigt“-Klicks werden lokal
   gespeichert und beim nächsten Netzkontakt automatisch synchronisiert.
6. **Immer absicherbar.** Backup per Knopfdruck herunterladen oder automatisch
   auf ein NAS mounten – siehe [Backup](#backup--wiederherstellung).

**Mehrere Personen im Haushalt:** Alle Geräte im selben Netz nutzen dieselbe
Installation (jeweils einmal das Zertifikat bestätigen, siehe unten). Wer etwas
erledigt, kann seinen Namen bei „Erledigt“ hinterlegen – so sieht die Familie,
wann und von wem was gemacht wurde.

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

Drei Wege – vom Einzeiler bis zur manuellen Variante.

### Variante 0 – Einzeiler (wie bei den bekannten Proxmox-Community-Skripten)

Auf dem Proxmox-Host als root ausführen – das lädt das Repository, erstellt den
Container, installiert alles und gibt am Ende die Adresse des Dashboards aus:

```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/HatchetMan111/HausMeisterCheckliste/main/hausmeister.sh)"
```

Vollautomatisch ohne Rückfragen (Standardeinstellungen: DHCP, Hostname
`hausmeister`, Storage automatisch ermittelt):

```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/HatchetMan111/HausMeisterCheckliste/main/hausmeister.sh)" -- --auto
```

Die Ausgabe am Ende enthält beide Adressen, unter denen das Dashboard erreichbar
ist – bevorzugt `https://hausmeister.local`, alternativ die Container-IP
(dort beim ersten Aufruf die Zertifikatswarnung bestätigen):

```
DASHBOARD (empfohlen) : https://hausmeister.local
DASHBOARD über IP     : https://192.168.1.50
```

Über Umgebungsvariablen lässt sich der Einzeiler anpassen, z. B.:

```bash
HAUSMEISTER_AUTO=1 HAUSMEISTER_PUSH_ENABLED=1 \
  bash -c "$(curl -fsSL https://raw.githubusercontent.com/HatchetMan111/HausMeisterCheckliste/main/hausmeister.sh)"
```

### Variante A – Komplett-Setup auf dem Proxmox-Host (interaktiv)

```bash
git clone https://github.com/HatchetMan111/HausMeisterCheckliste.git
cd HausMeisterCheckliste
bash ct/hausmeister.sh          # interaktiv (Vorgaben mit Enter übernehmen)
# oder: bash ct/hausmeister.sh --auto
```

Das Skript fragt interaktiv ab (alle Vorgaben mit Enter übernehmbar; DHCP ist
Standard und unproblematisch, da das Zertifikat am mDNS-Namen hängt):

- Container-Hostname (Standard: `hausmeister`)
- Netzwerk-Bridge (Standard: `vmbr0`)
- IP-Vergabe: **dhcp** oder **statisch** (bei statisch: IP/CIDR + Gateway)
- Storage für die Root-Disk
- Git-Repository-URL (voreingestellt: dieses Repository)
- Version/Tag (`latest` = höchster Release-Tag, Standard)
- Container-ID

Danach: Vorlage herunterladen, unprivilegierter Container erstellen
(`onboot=1`, 2 vCPU, 2 GB RAM, 8 GB), starten, Installer automatisch im
Container ausführen. Am Ende erscheinen Dashboard-Adresse und Container-IP.

### Variante B – vorhandenen Container/Server einrichten

Für Debian 12/13 (im LXC als root, sonst mit `sudo`):

```bash
git clone https://github.com/HatchetMan111/HausMeisterCheckliste.git
cd HausMeisterCheckliste
bash install/hausmeister-install.sh
```

Oder ohne vorheriges Klonen – das Skript lädt das Repository selbst:

```bash
HAUSMEISTER_REPO_URL=https://github.com/HatchetMan111/HausMeisterCheckliste.git \
  bash install/hausmeister-install.sh
```

Optionale Umgebungsvariablen (beide Varianten):

| Variable | Bedeutung | Standard |
|---|---|---|
| `HAUSMEISTER_REPO_URL` | zu installierendes Repository | dieses Repository |
| `HAUSMEISTER_VERSION` | Git-Tag, der installiert wird | `latest` (höchster Tag) |
| `HAUSMEISTER_AUTO` | `1` = ohne Rückfragen, alle Vorgaben übernehmen (alternativ `--auto`) | `0` |
| `HAUSMEISTER_NET_MODE` | `dhcp` oder `statisch` | `dhcp` |
| `HAUSMEISTER_CT_IP` / `HAUSMEISTER_CT_GW` | IP (CIDR) und Gateway bei `statisch` | – |
| `HAUSMEISTER_PUSH_ENABLED` | `1` = Web Push aktivieren | `0` |
| `HAUSMEISTER_APP_URL` | öffentliche Adresse (auch für Caddy-Zertifikat) | `https://hausmeister.local` |
| `HAUSMEISTER_TZ` | Zeitzone im Container | `Europe/Berlin` |

Beispiel mit eigener Domain und Push:

```bash
HAUSMEISTER_APP_URL=https://wartung.meine-familie.de \
HAUSMEISTER_PUSH_ENABLED=1 \
  bash install/hausmeister-install.sh
```

### Was der Container-Installer macht

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

## Erste Schritte nach der Installation

In ~10 Minuten vom frischen Container zur fertigen Nutzung:

1. **Dashboard öffnen – ohne jegliches Zertifikatsaufwand:**
   `http://hausmeister.local` (oder `http://<Container-IP>`).
   Über HTTP läuft alles: Aufgaben, Fälligkeiten, Verlauf, Einstellungen,
   Backup. Hinweis: Ob `.local`-Namen am PC/Handy funktionieren, hängt vom
   Gerät ab (mDNS) – die IP-Adresse funktioniert immer.
2. **Dashboard prüfen:** die Platzhalter-Aufgaben sind bereits geladen und
   erzeugen sofort erste Fälligkeiten – so siehst du sofort, wie alles arbeitet.
3. **Als App installieren + Offline-Modus + Push (optional):** dafür ist HTTPS
   mit bestätigtem Zertifikat nötig – ein einmaliger Schritt pro Gerät,
   Anleitung im nächsten Abschnitt. Danach die Seite über
   `https://hausmeister.local` nutzen und im Browser-Menü „Zum Startbildschirm
   hinzufügen“ / „App installieren“ wählen.
4. **Eigene Checkliste importieren** (oder Platzhalter anpassen), siehe
   [Checklisten-Import](#checklisten-import).
5. **E-Mail einrichten:** *Einstellungen → E-Mail-Benachrichtigung* – SMTP-Host,
   Empfänger eintragen, Kanal aktivieren, Test-E-Mail senden.
6. **Web Push** (optional, setzt Schritt 3 voraus), siehe
   [Web Push aktivieren](#web-push-aktivieren).
7. **Backup prüfen:** unter *Einstellungen → Backup* einmal den ZIP-Download
   ausführen und – empfohlen – ein externes Backup-Ziel mounten
   (siehe [Backup](#backup--wiederherstellung)).

Danach läuft der Betrieb von selbst: der tägliche Timer (07:30 Uhr) erzeugt
neue Fälligkeiten, sichert die Datenbank und schickt die E-Mail-Zusammenfassung.

**HTTP oder HTTPS?** Über HTTP nutzt du Hausmeister komplett im Browser – nur
die PWA-Extras (App-Installation, Offline-„Erledigt“-Klicks, Push) brauchen
HTTPS als „secure context“. HTTPS bleibt parallel aktiv; du kannst jederzeit
wechseln.

## Zertifikat auf deinem Gerät bestätigen (nur für Offline-Modus & Push)

Für die normale Nutzung reicht HTTP (`http://hausmeister.local` bzw.
`http://<Container-IP>`) – ganz ohne Zertifikat. HTTPS ist nur dann relevant,
wenn du die **PWA-Funktionen** willst: App-Installation auf dem Startbildschirm,
Offline-„Erledigt“-Klicks und Web Push. Browser verlangen dafür einen
„secure context“, also ein vertrautes Zertifikat.

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
git clone https://github.com/HatchetMan111/HausMeisterCheckliste.git
cd HausMeisterCheckliste
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

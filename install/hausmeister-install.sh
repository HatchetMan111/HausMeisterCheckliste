#!/usr/bin/env bash
# Hausmeister – Installation im Container (Debian 12/13)
# Läuft als root. Idempotent: erneutes Ausführen ist gefahrlos möglich.
set -Eeuo pipefail

APP_NAME="Hausmeister"
APP_DIR="/opt/hausmeister"
APP_USER="hausmeister"
LOG_FILE="/var/log/hausmeister-install-$(date +%Y%m%d-%H%M%S).log"
REPO_URL="${HAUSMEISTER_REPO_URL:-https://github.com/HatchetMan111/HausMeisterCheckliste.git}"
APP_VERSION="${HAUSMEISTER_VERSION:-latest}"
PUSH_ENABLED="${HAUSMEISTER_PUSH_ENABLED:-0}"
APP_PUBLIC_URL="${HAUSMEISTER_APP_URL:-https://hausmeister.local}"
TIMEZONE="${HAUSMEISTER_TZ:-Europe/Berlin}"

exec > >(tee -a "$LOG_FILE") 2>&1

export LANG=C.UTF-8
export LC_ALL=C.UTF-8

info()  { printf '\033[1;32m[INFO]\033[0m %s\n' "$*"; }
warn()  { printf '\033[1;33m[WARN]\033[0m %s\n' "$*"; }
fail()  { printf '\033[1;31m[FEHLER]\033[0m %s\n' "$*"; }

as_app_user() {
  runuser -u "$APP_USER" -- "$@"
}

on_error() {
  local code=$? cmd=${BASH_COMMAND:-unbekannt}
  fail "Installation fehlgeschlagen."
  fail "Fehlender Befehl : $cmd"
  fail "Exit-Code        : $code"
  fail "System           : $(uname -a)"
  fail "Vollständiges Log: $LOG_FILE"
  fail "Debug-Hinweis    : bash -x $0  (für detaillierte Ausgabe)"
  exit "$code"
}
trap on_error ERR

if [[ $EUID -ne 0 ]]; then
  fail "Bitte als root ausführen (im LXC)."
  exit 1
fi

if [[ -z "$REPO_URL" ]]; then
  read -r -e -p "Git-Repository-URL von $APP_NAME: " REPO_URL
  [[ -z "$REPO_URL" ]] && { fail "Repository-URL ist erforderlich."; exit 1; }
fi

info "=== $APP_NAME Installation (Version: $APP_VERSION) ==="

export DEBIAN_FRONTEND=noninteractive

info "System vorbereiten …"
apt-get update -qq
apt-get install -y -qq ca-certificates curl git python3 python3-venv sqlite3 avahi-daemon tzdata >/dev/null

info "Zeitzone setzen: $TIMEZONE"
if [[ -f "/usr/share/zoneinfo/$TIMEZONE" ]]; then
  ln -snf "/usr/share/zoneinfo/$TIMEZONE" /etc/localtime
  echo "$TIMEZONE" > /etc/timezone
else
  warn "Zeitzone $TIMEZONE unbekannt – Standard bleibt unverändert."
fi

info "Webserver (caddy) installieren …"
if ! command -v caddy >/dev/null 2>&1; then
  if ! apt-get install -y -qq caddy >/dev/null 2>&1; then
    info "caddy nicht im Standard-Repository – Paketquelle ergänzen …"
    apt-get install -y -qq debian-keyring debian-archive-keyring apt-transport-https >/dev/null
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --batch --yes --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' > /etc/apt/sources.list.d/caddy-stable.list
    apt-get update -qq
    apt-get install -y -qq caddy >/dev/null
  fi
fi

info "Systembenutzer $APP_USER anlegen …"
id -u "$APP_USER" >/dev/null 2>&1 || useradd --system --create-home --home-dir "/home/$APP_USER" --shell /usr/sbin/nologin "$APP_USER"

info "Anwendung nach $APP_DIR laden (Tag-basiert, kein Blind-Branch) …"
if [[ -d "$APP_DIR/.git" ]]; then
  git -C "$APP_DIR" fetch --all --tags --quiet
else
  git clone --quiet "$REPO_URL" "$APP_DIR"
fi

cd "$APP_DIR"
if [[ "$APP_VERSION" == "latest" ]]; then
  APP_VERSION="$(git -C "$APP_DIR" tag --list --sort=-v:refname | head -n1 || true)"
  if [[ -z "$APP_VERSION" ]]; then
    fail "Kein Git-Tag im Repository gefunden. Erwartet werden Tags (z. B. v0.1.0)."
    fail "Erstinstallation mit halbfertigen Zwischenständen wird bewusst verhindert."
    fail "Lösung: im Repository einen Release-Tag setzen oder HAUSMEISTER_VERSION=<tag> übergeben."
    exit 1
  fi
fi
git -C "$APP_DIR" checkout --quiet "tags/$APP_VERSION"
info "Aktiv: Version $APP_VERSION"

info "Python-Umgebung einrichten …"
if [[ ! -d "$APP_DIR/venv" ]]; then
  python3 -m venv "$APP_DIR/venv"
fi
"$APP_DIR/venv/bin/pip" install --quiet --upgrade pip
"$APP_DIR/venv/bin/pip" install --quiet -r "$APP_DIR/requirements.txt"

mkdir -p "$APP_DIR/data"
chown -R "$APP_USER:$APP_USER" "$APP_DIR"

info "Datenbankschema migrieren (Alembic) …"
as_app_user env HAUSMEISTER_DATA_DIR="$APP_DIR/data" \
  "$APP_DIR/venv/bin/alembic" -c "$APP_DIR/alembic.ini" upgrade head

info "Aufgabenbibliothek importieren (nur bei leerer Datenbank) …"
TASK_COUNT=$(as_app_user env HAUSMEISTER_DATA_DIR="$APP_DIR/data" \
  "$APP_DIR/venv/bin/python" - <<'PYEOF'
from app.db import init
init()
from app.db import SessionLocal
from app.models import Task
db = SessionLocal()
print(db.query(Task).count())
db.close()
PYEOF
) || TASK_COUNT=0
if [[ "${TASK_COUNT:-0}" -eq 0 ]]; then
  as_app_user env HAUSMEISTER_DATA_DIR="$APP_DIR/data" \
    "$APP_DIR/venv/bin/python" "$APP_DIR/scripts/import_checklist.py" "$APP_DIR/data/templates/checklist.json"
  info "Platzhalter-Aufgabenbibliothek importiert (vor Produktionseinsatz ersetzen!)."
else
  info "Datenbank enthält $TASK_COUNT Aufgaben – Import übersprungen."
fi

info "Umgebungsdatei .env schreiben …"
if [[ ! -f "$APP_DIR/.env" ]]; then
  cat > "$APP_DIR/.env" <<EOF
HAUSMEISTER_DATA_DIR=$APP_DIR/data
HAUSMEISTER_BACKUP_DIR=$APP_DIR/data/backups
HAUSMEISTER_PUSH_ENABLED=$PUSH_ENABLED
HAUSMEISTER_APP_URL=$APP_PUBLIC_URL
EOF
else
  sed -i "s|^HAUSMEISTER_PUSH_ENABLED=.*|HAUSMEISTER_PUSH_ENABLED=$PUSH_ENABLED|" "$APP_DIR/.env"
  sed -i "s|^HAUSMEISTER_APP_URL=.*|HAUSMEISTER_APP_URL=$APP_PUBLIC_URL|" "$APP_DIR/.env"
fi
chown "$APP_USER:$APP_USER" "$APP_DIR/.env"
chmod 600 "$APP_DIR/.env"

info "systemd-Units installieren …"
install -m 644 "$APP_DIR/systemd/hausmeister.service" /etc/systemd/system/hausmeister.service
install -m 644 "$APP_DIR/systemd/hausmeister-daily.service" /etc/systemd/system/hausmeister-daily.service
install -m 644 "$APP_DIR/systemd/hausmeister-daily.timer" /etc/systemd/system/hausmeister-daily.timer
install -m 644 "$APP_DIR/systemd/caddy.service" /etc/systemd/system/caddy.service
systemctl daemon-reload

info "Caddy-Konfiguration (TLS auf $APP_PUBLIC_URL) …"
install -d -o caddy -g caddy /etc/caddy
if [[ "$APP_PUBLIC_URL" != "https://hausmeister.local" && "$APP_PUBLIC_URL" != "hausmeister.local" ]]; then
  SITE_NAME="${APP_PUBLIC_URL#https://}"
  SITE_NAME="${SITE_NAME%%/*}"
else
  SITE_NAME="hausmeister.local"
fi
if [[ ! -f /etc/caddy/Caddyfile ]]; then
  cat > /etc/caddy/Caddyfile <<EOF
{
\tadmin off
}

$SITE_NAME {
\ttls internal
\tencode gzip
\treverse_proxy 127.0.0.1:8080
}
EOF
fi

info "Dienste starten und aktivieren …"
systemctl enable --now avahi-daemon >/dev/null 2>&1 || true
systemctl enable --now caddy
systemctl enable --now hausmeister
systemctl enable --now hausmeister-daily.timer

info "Warten auf die Anwendung …"
for _ in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:8080/health >/dev/null 2>&1; then break; fi
  sleep 1
done

info "Root-CA des internen Zertifikats exportieren (für lokale Verifikation) …"
CA_SRC="/var/lib/caddy/.local/share/caddy/pki/authorities/local/root.crt"
for _ in $(seq 1 15); do
  [[ -f "$CA_SRC" ]] && break
  curl -ksSf "https://127.0.0.1/" -o /dev/null >/dev/null 2>&1 || true
  sleep 2
done
if [[ -f "$CA_SRC" ]]; then
  install -d -m 755 "$APP_DIR/data/certs"
  install -m 644 "$CA_SRC" "$APP_DIR/data/certs/root-ca.crt"
  install -m 644 "$CA_SRC" /usr/local/share/ca-certificates/hausmeister-root-ca.crt
  update-ca-certificates >/dev/null 2>&1 || true
  info "Root-CA lokal vertraut (Container-intern)."
else
  warn "Root-CA noch nicht vorhanden – Geräte-Anleitung unter https://$SITE_NAME/help/certificate beachten."
fi

info "=== Verifikation ==="
FAILED=0
for UNIT in hausmeister caddy; do
  if systemctl is-active --quiet "$UNIT"; then
    info "Service aktiv : $UNIT"
  else
    fail "Service inaktiv: $UNIT"
    FAILED=1
  fi
done
if systemctl is-enabled --quiet hausmeister-daily.timer && systemctl is-active --quiet hausmeister-daily.timer; then
  info "Timer aktiv   : hausmeister-daily.timer ($(systemctl show -p NextElapseUSecRealtime --value hausmeister-daily.timer))"
else
  fail "Timer nicht aktiv: hausmeister-daily.timer"
  FAILED=1
fi
if curl -fsS "https://$SITE_NAME/health" >/dev/null 2>&1 \
  || curl -fsS --resolve "$SITE_NAME:443:127.0.0.1" "https://$SITE_NAME/health" >/dev/null 2>&1; then
  info "Health-Check  : https://$SITE_NAME/health → OK"
else
  fail "Health-Check fehlgeschlagen: https://$SITE_NAME/health"
  FAILED=1
fi

CT_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
if [[ $FAILED -eq 1 ]]; then
  fail "Installation mit Fehlern abgeschlossen – Log: $LOG_FILE"
  exit 1
fi

cat <<EOF

============================================================
 $APP_NAME ist installiert (Version $APP_VERSION).

  Adresse        : https://$SITE_NAME
  Container-IP   : ${CT_IP:-unbekannt}  (mDNS: $SITE_NAME)
  Health         : https://$SITE_NAME/health

  WICHTIG – Zertifikat bestätigen (pro Gerät einmalig):
    1. https://$SITE_NAME im Browser öffnen und der Warnung
       vorübergehend folgen ('Erweitert' > 'Weiter zu ...').
    2. Root-CA laden: https://$SITE_NAME/certs/root-ca.crt
    3. Schritt-für-Schritt-Anleitung (Android/iOS/Windows/Linux):
       https://$SITE_NAME/help/certificate
    Ohne diesen Schritt bleiben Service-Worker (Offline-Modus)
    und Web Push deaktiviert.

  Nächste Schritte:
    - E-Mail/SMTP in der Web-UI eintragen (Einstellungen).
    - Platzhalter-Aufgaben durch echte Checklisten ersetzen:
      $APP_DIR/venv/bin/python $APP_DIR/scripts/import_checklist.py <datei.json|csv>
    - Web Push aktivieren (optional): README, Abschnitt 'Web Push aktivieren'.

  Log: $LOG_FILE
============================================================
EOF

#!/usr/bin/env bash
# Hausmeister – Update auf den höchsten Release-Tag (kein Blind-Branch-Pull)
set -Eeuo pipefail

APP_DIR="/opt/hausmeister"
LOG_FILE="/var/log/hausmeister-update-$(date +%Y%m%d-%H%M%S).log"
exec > >(tee -a "$LOG_FILE") 2>&1

info()  { printf '\033[1;32m[INFO]\033[0m %s\n' "$*"; }
fail()  { printf '\033[1;31m[FEHLER]\033[0m %s\n' "$*"; }

on_error() {
  local code=$? cmd=${BASH_COMMAND:-unbekannt}
  fail "Update abgebrochen: '$cmd' (Exit $code)"
  fail "Log: $LOG_FILE"
  fail "Debug: bash -x $0"
  exit "$code"
}
trap on_error ERR

if [[ $EUID -ne 0 ]]; then
  fail "Bitte als root ausführen (im LXC)."
  exit 1
fi
if [[ ! -d "$APP_DIR/.git" ]]; then
  fail "$APP_DIR ist keine Installation von Hausmeister."
  exit 1
fi

CURRENT=$(git -C "$APP_DIR" describe --tags --exact-match 2>/dev/null || git -C "$APP_DIR" rev-parse --short HEAD)
info "Aktuelle Version: $CURRENT"

git -C "$APP_DIR" fetch --all --tags --quiet
LATEST=$(git -C "$APP_DIR" tag --list --sort=-v:refname | head -n1)
if [[ -z "$LATEST" ]]; then
  fail "Keine Tags im Repository gefunden – Update wird abgebrochen."
  exit 1
fi

if [[ "$LATEST" == "$CURRENT" ]]; then
  info "Bereits auf höchstem Tag ($LATEST). Nichts zu tun."
  exit 0
fi

info "Vor dem Update: Datenbank sichern …"
"$APP_DIR/venv/bin/python" - <<PYEOF
from app.config import ensure_dirs
from app.services.scheduler import backup_db
ensure_dirs()
print("Backup:", backup_db())
PYEOF

info "Wechsle zu Tag $LATEST …"
git -C "$APP_DIR" checkout --quiet "tags/$LATEST"

if [[ -f "$APP_DIR/requirements.txt" ]]; then
  "$APP_DIR/venv/bin/pip" install --quiet -r "$APP_DIR/requirements.txt"
fi

info "Migrationen anwenden …"
runuser -u hausmeister -- env HAUSMEISTER_DATA_DIR="$APP_DIR/data" \
  "$APP_DIR/venv/bin/alembic" -c "$APP_DIR/alembic.ini" upgrade head

systemctl restart hausmeister

info "Verifikation …"
for _ in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:8080/health >/dev/null 2>&1; then break; fi
  sleep 1
done
if curl -fsS https://hausmeister.local/health >/dev/null 2>&1 \
  || curl -fsS --resolve hausmeister.local:443:127.0.0.1 https://hausmeister.local/health >/dev/null 2>&1; then
  info "Health-Check OK."
else
  fail "Health-Check fehlgeschlagen – Dienste prüfen (systemctl status hausmeister)."
  exit 1
fi

systemctl is-active --quiet hausmeister && info "Service: hausmeister aktiv"
systemctl is-active --quiet caddy && info "Service: caddy aktiv"
systemctl is-active --quiet hausmeister-daily.timer && info "Timer: hausmeister-daily.timer aktiv"

info "Update abgeschlossen: $CURRENT → $LATEST (Log: $LOG_FILE)"

#!/usr/bin/env bash
# Hausmeister – Einzeiler-Installation auf einem Proxmox-Host
#
# Interaktiv (Vorgaben mit Enter übernehmen):
#   bash -c "$(curl -fsSL https://raw.githubusercontent.com/HatchetMan111/HausMeisterCheckliste/main/hausmeister.sh)"
# Vollautomatisch (Standardeinstellungen, DHCP):
#   bash -c "$(curl -fsSL https://raw.githubusercontent.com/HatchetMan111/HausMeisterCheckliste/main/hausmeister.sh)" -- --auto
#
# Am Ende wird die Adresse des Dashboards ausgegeben (hausmeister.local und Container-IP).
set -Eeuo pipefail

REPO_URL="${HAUSMEISTER_REPO_URL:-https://github.com/HatchetMan111/HausMeisterCheckliste.git}"

info()  { printf '\033[1;32m[INFO]\033[0m %s\n' "$*"; }
fail()  { printf '\033[1;31m[FEHLER]\033[0m %s\n' "$*"; }

on_error() {
  local code=$? cmd=${BASH_COMMAND:-unbekannt}
  fail "Abbruch: '$cmd' (Exit $code)"
  fail "Debug: bash -x $0"
  exit "$code"
}
trap on_error ERR

if [[ $EUID -ne 0 ]]; then
  fail "Bitte als root auf dem Proxmox-Host ausführen."
  exit 1
fi
if ! command -v pct >/dev/null 2>&1; then
  fail "pct nicht gefunden – dieser Einzeiler gehört auf einen Proxmox-Host."
  fail "Für einen vorhandenen Container/Server siehe README (install/hausmeister-install.sh)."
  exit 1
fi

WORK_DIR=$(mktemp -d /tmp/hausmeister-setup.XXXXXX)
cleanup() { rm -rf "$WORK_DIR"; }
trap cleanup EXIT

info "Repository laden: $REPO_URL …"
if command -v git >/dev/null 2>&1; then
  git clone --quiet "$REPO_URL" "$WORK_DIR/repo"
else
  info "git nicht gefunden – Archiv-Download als Ausweichweg …"
  mkdir -p "$WORK_DIR/repo"
  ARCHIVE_URL="${REPO_URL%.git}/archive/refs/heads/main.tar.gz"
  curl -fsSL "$ARCHIVE_URL" | tar xz -C "$WORK_DIR/repo" --strip-components=1
fi

if [[ "${HAUSMEISTER_VERSION:-latest}" == "latest" ]]; then
  git -C "$WORK_DIR/repo" fetch --tags --quiet 2>/dev/null || true
  LATEST_TAG=$(git -C "$WORK_DIR/repo" tag --list --sort=-v:refname | head -n1 || true)
  if [[ -n "$LATEST_TAG" ]]; then
    git -C "$WORK_DIR/repo" checkout --quiet "tags/$LATEST_TAG"
    info "Release-Tag aktiv: $LATEST_TAG"
  fi
else
  git -C "$WORK_DIR/repo" checkout --quiet "tags/${HAUSMEISTER_VERSION}"
  info "Release-Tag aktiv: ${HAUSMEISTER_VERSION}"
fi

bash "$WORK_DIR/repo/ct/hausmeister.sh" "$@"

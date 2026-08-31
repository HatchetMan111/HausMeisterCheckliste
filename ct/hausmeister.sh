#!/usr/bin/env bash
# Hausmeister – LXC-Erstellung auf dem Proxmox-Host (unprivilegiert, Debian 13)
# Erstellt Container, installiert die Anwendung und gibt am Ende die Adresse des
# Dashboards aus.
#
# Interaktiv (alle Vorgaben mit Enter übernehmen):
#   bash ct/hausmeister.sh
# Vollautomatisch mit Standardeinstellungen (DHCP, hausmeister.local):
#   bash ct/hausmeister.sh --auto
#   HAUSMEISTER_AUTO=1 bash ct/hausmeister.sh
set -Eeuo pipefail

APP_NAME="Hausmeister"
AUTO=0
if [[ "${1:-}" == "--auto" || "${HAUSMEISTER_AUTO:-0}" == "1" ]]; then
  AUTO=1
fi

HN="hausmeister"
BRIDGE="vmbr0"
NET_MODE="${HAUSMEISTER_NET_MODE:-dhcp}"
CT_IP="${HAUSMEISTER_CT_IP:-}"
CT_GW="${HAUSMEISTER_CT_GW:-}"
STORAGE=""
CTID=""
CORES="${HAUSMEISTER_CORES:-2}"
MEM="${HAUSMEISTER_MEM:-2048}"
DISK="${HAUSMEISTER_DISK:-8}"
INSTALL_SCRIPT="$(cd "$(dirname "$0")/.." && pwd)/install/hausmeister-install.sh"
REPO_URL="${HAUSMEISTER_REPO_URL:-https://github.com/HatchetMan111/HausMeisterCheckliste.git}"
APP_VERSION="${HAUSMEISTER_VERSION:-latest}"
PUSH_ENABLED="${HAUSMEISTER_PUSH_ENABLED:-0}"
LOG_FILE="/var/log/hausmeister-ct-$(date +%Y%m%d-%H%M%S).log"

exec > >(tee -a "$LOG_FILE") 2>&1

info()  { printf '\033[1;32m[INFO]\033[0m %s\n' "$*"; }
warn()  { printf '\033[1;33m[WARN]\033[0m %s\n' "$*"; }
fail()  { printf '\033[1;31m[FEHLER]\033[0m %s\n' "$*"; }

ask() {
  local -n _out=$1
  local _default=$2 _prompt=$3 _input=""
  if [[ $AUTO -eq 1 ]]; then
    info "$_prompt: $_default (Auto-Modus)"
    _out=$_default
  else
    read -r -p "$_prompt [$_default]: " _input
    _out="${_input:-$_default}"
  fi
}

on_error() {
  local code=$? cmd=${BASH_COMMAND:-unbekannt}
  fail "Abbruch."
  fail "Befehl           : $cmd"
  fail "Exit-Code        : $code"
  fail "STDOUT/STDERR    : siehe oben / Log"
  fail "System           : $(uname -a)"
  fail "Vollständiges Log: $LOG_FILE"
  fail "Debug-Hinweis    : bash -x $0"
  if [[ -n "$CTID" ]] && pct status "$CTID" >/dev/null 2>&1; then
    warn "Container $CTID wurde nicht gelöscht – für Fehlersuche dort weiterarbeiten."
  fi
  exit "$code"
}
trap on_error ERR

if [[ $EUID -ne 0 ]]; then
  fail "Bitte als root auf dem Proxmox-Host ausführen."
  exit 1
fi
if ! command -v pct >/dev/null 2>&1; then
  fail "pct nicht gefunden – dieses Skript gehört auf einen Proxmox-Host."
  exit 1
fi
if [[ ! -f "$INSTALL_SCRIPT" ]]; then
  fail "Installer nicht gefunden: $INSTALL_SCRIPT"
  exit 1
fi

echo "=== $APP_NAME – LXC-Setup ==="
if [[ $AUTO -eq 1 ]]; then
  info "Auto-Modus: alle Vorgaben werden übernommen (Netzwerk: $NET_MODE)."
fi
echo ""

ask HN "$HN" "Container-Hostname"
ask BRIDGE "$BRIDGE" "Netzwerk-Bridge"

if [[ -n "${HAUSMEISTER_NET_MODE:-}" ]]; then
  info "Netzwerk-Modus aus Umgebungsvariable: $NET_MODE"
elif [[ $AUTO -eq 1 ]]; then
  info "IP-Vergabe: dhcp (Auto-Modus – möglich, da das Zertifikat am mDNS-Namen hängt)"
else
  while true; do
    read -r -p "IP-Vergabe: dhcp oder statisch [dhcp]: " INPUT
    NET_MODE="${INPUT:-dhcp}"
    [[ "$NET_MODE" == "dhcp" || "$NET_MODE" == "statisch" ]] && break
    warn "Bitte 'dhcp' oder 'statisch' eingeben."
  done
fi

if [[ "$NET_MODE" == "statisch" ]]; then
  if [[ -n "$CT_IP" && -n "$CT_GW" ]]; then
    info "Statische IP aus Umgebungsvariable: $CT_IP (GW $CT_GW)"
  else
    read -r -p "Statische IP (CIDR, z. B. 192.168.1.50/24): " CT_IP
    [[ -z "$CT_IP" ]] && { fail "Statische IP ist erforderlich."; exit 1; }
    read -r -p "Gateway (z. B. 192.168.1.1): " CT_GW
    [[ -z "$CT_GW" ]] && { fail "Gateway ist erforderlich."; exit 1; }
  fi
fi
echo "Hinweis: Das TLS-Zertifikat hängt am mDNS-Namen ($HN.local), nicht an der IP –"
echo "daher ist DHCP problemlos möglich. Die statische IP ist nur Komfort."

STORAGE_DEFAULT=$(pvesm status -content rootdir 2>/dev/null | awk 'NR>1 && $1!="Name" {print $1; exit}')
STORAGE_DEFAULT="${STORAGE_DEFAULT:-local-lvm}"
ask STORAGE "$STORAGE_DEFAULT" "Storage für Root-Disk (Container-Festplatte)"

TEMPLATE_STORAGE="${HAUSMEISTER_TEMPLATE_STORAGE:-}"
if [[ -z "$TEMPLATE_STORAGE" ]]; then
  TEMPLATE_STORAGE=$(pvesm status -content vztmpl 2>/dev/null | awk 'NR>1 && $1!="Name" {print $1; exit}' || true)
fi
if [[ -z "$TEMPLATE_STORAGE" ]]; then
  fail "Kein Storage mit Vorlagen-Unterstützung (Content 'vztmpl') gefunden."
  fail "Datacenter → Storage prüfen; alternativ HAUSMEISTER_TEMPLATE_STORAGE setzen."
  exit 1
fi
info "Vorlagen-Storage: $TEMPLATE_STORAGE"

read -r -p "Git-Repository-URL von $APP_NAME [${REPO_URL}]: " INPUT
REPO_URL="${INPUT:-$REPO_URL}"
[[ -z "$REPO_URL" ]] && { fail "Repository-URL ist erforderlich."; exit 1; }
ask APP_VERSION "$APP_VERSION" "Version/Tag (latest = höchster Release-Tag)"

CTID_DEFAULT=$(pvesh get /cluster/nextid 2>/dev/null || true)
if [[ -z "$CTID_DEFAULT" ]]; then
  CTID_DEFAULT=200
  while pct list 2>/dev/null | awk '{print $1}' | grep -qx "$CTID_DEFAULT" \
    || qm list 2>/dev/null | awk '{print $1}' | grep -qx "$CTID_DEFAULT"; do
    CTID_DEFAULT=$((CTID_DEFAULT + 1))
  done
fi
ask CTID "$CTID_DEFAULT" "Container-ID"
if pct list 2>/dev/null | awk '{print $1}' | grep -qx "$CTID" \
  || qm list 2>/dev/null | awk '{print $1}' | grep -qx "$CTID"; then
  fail "ID $CTID ist bereits vergeben (Container oder VM)."
  exit 1
fi

info "Debian-13-Vorlage herunterladen …"
pveam update >/dev/null 2>&1 || true
TEMPLATE=$(pveam available 2>/dev/null | awk '{print $2}' | grep '^debian-13-standard' | sort -V | tail -n1 || true)
if [[ -z "$TEMPLATE" ]]; then
  warn "Keine Debian-13-Vorlage gefunden – Debian-12-Vorlage wird verwendet."
  TEMPLATE=$(pveam available 2>/dev/null | awk '{print $2}' | grep '^debian-12-standard' | sort -V | tail -n1 || true)
fi
if [[ -z "$TEMPLATE" ]]; then
  fail "Keine Debian-Standardvorlage gefunden."
  fail "Bitte manuell prüfen: pveam available  (erwartet: debian-1x-standard_*)"
  exit 1
fi
pveam download "$TEMPLATE_STORAGE" "$TEMPLATE" >/dev/null || { fail "Vorlagen-Download fehlgeschlagen: $TEMPLATE (Storage: $TEMPLATE_STORAGE)"; exit 1; }
info "Vorlage: $TEMPLATE"

info "Container $CTID erstellen (unprivilegiert, onboot=1, ${CORES} vCPU, ${MEM}MB RAM, ${DISK}GB) …"
NET_CFG="name=eth0,bridge=$BRIDGE,firewall=0"
if [[ "$NET_MODE" == "statisch" ]]; then
  NET_CFG+=",ip=$CT_IP,gw=$CT_GW"
else
  NET_CFG+=",ip=dhcp"
fi

pct create "$CTID" "${TEMPLATE_STORAGE}:vztmpl/$TEMPLATE" \
  --hostname "$HN" \
  --unprivileged 1 \
  --onboot 1 \
  --cores "$CORES" \
  --memory "$MEM" \
  --swap 512 \
  --rootfs "${STORAGE}:${DISK}" \
  --net0 "$NET_CFG" \
  --features nesting=0 \
  --start 0 >/dev/null

info "Container starten und auf Netzwerk warten …"
pct start "$CTID"
for _ in $(seq 1 30); do
  if pct exec "$CTID" -- sh -c 'ip -4 addr show dev eth0 | grep -q inet' 2>/dev/null; then
    break
  fi
  sleep 2
done

info "Installer in den Container pushen und ausführen …"
pct push "$CTID" "$INSTALL_SCRIPT" /tmp/hausmeister-install.sh --perms 755
pct exec "$CTID" -- bash -c \
  "HAUSMEISTER_REPO_URL='$REPO_URL' HAUSMEISTER_VERSION='$APP_VERSION' HAUSMEISTER_PUSH_ENABLED='$PUSH_ENABLED' bash /tmp/hausmeister-install.sh"

CT_ACTUAL_IP=$(pct exec "$CTID" -- hostname -I 2>/dev/null | awk '{print $1}' || true)
info "=== Fertig ==="
cat <<EOF

  ============================================================
   $APP_NAME ist installiert und läuft.

    DASHBOARD (sofort, ohne Zertifikat) : http://$HN.local
    DASHBOARD über IP                   : http://${CT_ACTUAL_IP:-unbekannt}

    DASHBOARD mit PWA-Funktionen        : https://$HN.local
      (Offline-Modus/Push – dafür einmalig Zertifikat
       bestätigen: https://$HN.local/help/certificate)

    Container-ID                        : $CTID
    Hostname                            : $HN (mDNS: $HN.local)
    Container-IP                        : ${CT_ACTUAL_IP:-unbekannt}
    Version                             : $APP_VERSION

    Log: $LOG_FILE
  ============================================================
EOF

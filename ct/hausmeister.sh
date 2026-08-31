#!/usr/bin/env bash
# Hausmeister – LXC-Erstellung auf dem Proxmox-Host (unprivilegiert, Debian 13)
# Fragt Netzwerk (DHCP/statisch), Bridge, Hostname und Storage interaktiv ab,
# erstellt den Container und führt anschließend install/hausmeister-install.sh aus.
set -Eeuo pipefail

APP_NAME="Hausmeister"
CTID=""
HN="hausmeister"
BRIDGE="vmbr0"
STORAGE=""
NET_MODE="dhcp"
CT_IP=""
CT_GW=""
CORES=2
MEM=2048
DISK=8
INSTALL_SCRIPT="$(cd "$(dirname "$0")/.." && pwd)/install/hausmeister-install.sh"
REPO_URL="${HAUSMEISTER_REPO_URL:-}"
APP_VERSION="${HAUSMEISTER_VERSION:-latest}"
PUSH_ENABLED="${HAUSMEISTER_PUSH_ENABLED:-0}"
LOG_FILE="/var/log/hausmeister-ct-$(date +%Y%m%d-%H%M%S).log"

exec > >(tee -a "$LOG_FILE") 2>&1

info()  { printf '\033[1;32m[INFO]\033[0m %s\n' "$*"; }
warn()  { printf '\033[1;33m[WARN]\033[0m %s\n' "$*"; }
fail()  { printf '\033[1;31m[FEHLER]\033[0m %s\n' "$*"; }

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
echo ""

read -r -e -p "Container-Hostname [$HN]: " INPUT && [[ -n "$INPUT" ]] && HN="$INPUT"

read -r -e -p "Netzwerk-Bridge [$BRIDGE]: " INPUT && [[ -n "$INPUT" ]] && BRIDGE="$INPUT"

while true; do
  read -r -e -p "IP-Vergabe: dhcp oder statisch [dhcp]: " INPUT
  INPUT="${INPUT:-dhcp}"
  [[ "$INPUT" == "dhcp" || "$INPUT" == "statisch" ]] && NET_MODE="$INPUT" && break
  warn "Bitte 'dhcp' oder 'statisch' eingeben."
done
if [[ "$NET_MODE" == "statisch" ]]; then
  read -r -e -p "Statische IP (CIDR, z. B. 192.168.1.50/24): " CT_IP
  [[ -z "$CT_IP" ]] && { fail "Statische IP ist erforderlich."; exit 1; }
  read -r -e -p "Gateway (z. B. 192.168.1.1): " CT_GW
  [[ -z "$CT_GW" ]] && { fail "Gateway ist erforderlich."; exit 1; }
fi
echo "Hinweis: Das TLS-Zertifikat hängt am mDNS-Namen ($HN.local), nicht an der IP –"
echo "daher ist DHCP problemlos möglich. Die statische IP ist nur Komfort."

STORAGE_DEFAULT=$(pvesm status -content rootdir 2>/dev/null | awk 'NR>1 && $1!="Name" {print $1; exit}')
STORAGE_DEFAULT="${STORAGE_DEFAULT:-local-lvm}"
read -r -e -p "Storage für Root-Disk [$STORAGE_DEFAULT]: " INPUT && STORAGE="${INPUT:-$STORAGE_DEFAULT}"

read -r -e -p "Git-Repository-URL von $APP_NAME: " REPO_URL
[[ -z "$REPO_URL" ]] && { fail "Repository-URL ist erforderlich."; exit 1; }
read -r -e -p "Version/Tag [latest = höchster Release-Tag]: " INPUT && APP_VERSION="${INPUT:-latest}"

CTID_DEFAULT=200
while pct list 2>/dev/null | awk '{print $1}' | grep -qx "$CTID_DEFAULT"; do
  CTID_DEFAULT=$((CTID_DEFAULT + 1))
done
read -r -e -p "Container-ID [$CTID_DEFAULT]: " INPUT && CTID="${INPUT:-$CTID_DEFAULT}"
if pct list 2>/dev/null | awk '{print $1}' | grep -qx "$CTID"; then
  fail "Container-ID $CTID ist bereits vergeben."
  exit 1
fi

info "Debian-13-Vorlage herunterladen …"
pveam update >/dev/null 2>&1 || true
TEMPLATE=$(pveam available --section system 2>/dev/null | awk '{print $2}' | grep '^debian-13-standard' | sort -V | tail -n1)
if [[ -z "$TEMPLATE" ]]; then
  TEMPLATE=$(pveam available 2>/dev/null | awk '{print $2}' | grep '^debian-1[23]-standard' | sort -V | tail -n1)
fi
[[ -z "$TEMPLATE" ]] && { fail "Keine Debian-Standardvorlage gefunden."; exit 1; }
pveam download "$STORAGE" "$TEMPLATE" >/dev/null
info "Vorlage: $TEMPLATE"

info "Container $CTID erstellen (unprivilegiert, onboot=1, ${CORES} vCPU, ${MEM}MB RAM, ${DISK}GB) …"
NET_CFG="name=eth0,bridge=$BRIDGE,firewall=0"
if [[ "$NET_MODE" == "statisch" ]]; then
  NET_CFG+=",ip=$CT_IP,gw=$CT_GW"
else
  NET_CFG+=",ip=dhcp"
fi

pct create "$CTID" "${STORAGE}:vztmpl/$TEMPLATE" \
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

CT_ACTUAL_IP=$(pct exec "$CTID" -- hostname -I 2>/dev/null | awk '{print $1}')
info "=== Fertig ==="
cat <<EOF

  Container-ID   : $CTID
  Hostname       : $HN (mDNS: $HN.local)
  IP             : ${CT_ACTUAL_IP:-unbekannt}
  URL            : https://$HN.local
  Version        : $APP_VERSION

  Nächster Schritt: Zertifikat pro Gerät bestätigen – Anleitung unter
  https://$HN.local/help/certificate (beim ersten Aufruf verlinkt).

  Log: $LOG_FILE
EOF

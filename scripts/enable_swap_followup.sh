#!/usr/bin/env bash
# Activa un archivo de swap de 2G en /swapfile (VMs pequeñas sin swap).
# Idempotente: si ya hay swap activo, no hace nada.
# Requiere: sudo
#
# Uso en servidor: sudo ./scripts/enable_swap_followup.sh

set -euo pipefail

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Ejecuta con sudo: sudo $0" >&2
  exit 1
fi

if swapon --show 2>/dev/null | grep -q .; then
  echo "Swap ya activo:"
  swapon --show
  free -h
  exit 0
fi

if [[ -f /swapfile ]] && swapon /swapfile 2>/dev/null; then
  echo "Reactivado /swapfile existente."
else
  [[ -f /swapfile ]] && rm -f /swapfile
  if command -v fallocate >/dev/null 2>&1; then
    fallocate -l 2G /swapfile
  else
    dd if=/dev/zero of=/swapfile bs=1M count=2048 status=none
  fi
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  echo "Creado /swapfile (2G) y activado."
fi

if ! grep -q '^/swapfile ' /etc/fstab; then
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
  echo "Añadido a /etc/fstab (persistente tras reinicio)."
fi

echo "vm.swappiness=10" >/etc/sysctl.d/99-followup-swappiness.conf
sysctl -p /etc/sysctl.d/99-followup-swappiness.conf

free -h
swapon --show

#!/usr/bin/env bash
# Comprueba que todo lo necesario esta instalado y que hay memoria suficiente.
ok=0
chk() { if command -v "$1" >/dev/null; then printf '  [ok] %s\n' "$1"; else printf '  [FALTA] %s\n' "$1"; ok=1; fi; }
echo "Herramientas:"; for t in git docker minikube kubectl k6 python3; do chk "$t"; done
echo "Recursos visibles en WSL:"
echo "  CPUs: $(nproc)   RAM: $(free -m | awk '/Mem:/{print $2}') MB   Swap: $(free -m | awk '/Swap:/{print $2}') MB"
if [ "$(free -m | awk '/Mem:/{print $2}')" -lt 3500 ]; then echo "  [AVISO] menos de 3.5 GB: revisa C:\\Users\\TU_USUARIO\\.wslconfig"; ok=1; fi
if docker info >/dev/null 2>&1; then echo "  [ok] Docker responde"; else echo "  [FALLA] Docker no responde (systemctl status docker / reabrir terminal)"; ok=1; fi
case "$PWD" in /mnt/*) echo "  [AVISO] estas en /mnt/c: clona el repo en ~/ (mucho mas rapido)"; ok=1;; esac
exit $ok

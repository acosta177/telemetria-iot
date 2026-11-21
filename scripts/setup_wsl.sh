#!/usr/bin/env bash
# Instala Docker Engine, kubectl, Minikube, k6 y Python en Ubuntu (WSL2).
# Requisito previo: systemd activado en /etc/wsl.conf (ver docs/GUIA_ENTORNO_WINDOWS.md).
set -euo pipefail

echo ">> Paquetes base"
sudo apt-get update
sudo apt-get install -y git curl ca-certificates gnupg python3-pip python3-venv conntrack

if ! command -v docker >/dev/null; then
  echo ">> Docker Engine"
  curl -fsSL https://get.docker.com | sh
  sudo usermod -aG docker "$USER"
fi
sudo systemctl enable --now docker || echo "AVISO: activa systemd en /etc/wsl.conf y ejecuta 'wsl --shutdown'"

if ! command -v kubectl >/dev/null; then
  echo ">> kubectl"
  curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
  sudo install kubectl /usr/local/bin/kubectl && rm kubectl
fi

if ! command -v minikube >/dev/null; then
  echo ">> Minikube"
  curl -LO https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64
  sudo install minikube-linux-amd64 /usr/local/bin/minikube && rm minikube-linux-amd64
fi

if ! command -v k6 >/dev/null; then
  echo ">> k6 (repositorio oficial)"
  sudo gpg -k >/dev/null 2>&1 || true
  sudo gpg --no-default-keyring --keyring /usr/share/keyrings/k6-archive-keyring.gpg \
    --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69
  echo "deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] https://dl.k6.io/deb stable main" \
    | sudo tee /etc/apt/sources.list.d/k6.list
  sudo apt-get update && sudo apt-get install -y k6
fi

echo ">> Entorno virtual de Python"
python3 -m venv .venv
.venv/bin/pip install -q -r requirements-dev.txt

echo
echo "LISTO. Cierra y vuelve a abrir la terminal (para el grupo docker) y ejecuta: bash scripts/verificar_entorno.sh"

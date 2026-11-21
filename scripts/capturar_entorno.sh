#!/usr/bin/env bash
# Guarda las condiciones del equipo (el PDF pide registrarlas junto a los resultados).
cd "$(dirname "$0")/.."
mkdir -p results
OUT=results/entorno.txt
{
  echo "Fecha UTC: $(date -u +%FT%TZ)"
  echo "Kernel: $(uname -r)"
  echo "CPUs visibles: $(nproc)"
  grep -m1 'model name' /proc/cpuinfo || true
  free -h
  echo "Docker: $(docker --version 2>&1)"
  echo "Minikube: $(minikube version --short 2>&1)"
  echo "kubectl: $(kubectl version --client 2>&1 | head -1)"
  echo "Kubernetes (servidor): $(kubectl version 2>&1 | grep -i server || true)"
  echo "k6: $(k6 version 2>&1)"
  echo "Nodo:"; kubectl get nodes -o wide 2>&1
  echo "Recursos del nodo:"; kubectl describe node 2>&1 | grep -A6 -E '^Capacity|^Allocatable'
  echo "Pods:"; kubectl -n telemetria-iot get pods -o wide 2>&1
  echo "Commit: $(git rev-parse --short HEAD 2>/dev/null)"
  echo "NOTA: anota tambien a mano que programas de Windows estaban abiertos."
} | tee "$OUT"

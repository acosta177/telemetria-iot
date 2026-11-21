#!/usr/bin/env bash
# Despliega todo en Minikube. Se puede ejecutar de nuevo tras cambiar codigo (reconstruye imagenes).
set -euo pipefail
cd "$(dirname "$0")/.."
NS=telemetria-iot
DB_PASSWORD="${DB_PASSWORD:-cambiar_contrasena_local}"
MINIKUBE_CPUS="${MINIKUBE_CPUS:-3}"
MINIKUBE_MEMORY="${MINIKUBE_MEMORY:-2800mb}"

for c in docker minikube kubectl; do
  command -v "$c" >/dev/null || { echo "Falta instalar $c (ver docs/GUIA_ENTORNO_WINDOWS.md)" >&2; exit 1; }
done

if ! minikube status >/dev/null 2>&1; then
  echo ">> Iniciando Minikube ($MINIKUBE_CPUS CPUs, $MINIKUBE_MEMORY)"
  minikube start --driver=docker --cpus="$MINIKUBE_CPUS" --memory="$MINIKUBE_MEMORY"
fi
minikube addons enable metrics-server >/dev/null || true

kubectl apply -f k8s/00_namespace.yaml
kubectl -n "$NS" create secret generic postgres-secret \
  --from-literal=password="$DB_PASSWORD" --dry-run=client -o yaml | kubectl apply -f -
kubectl -n "$NS" create configmap postgres-init \
  --from-file=001_schema.sql=db/init/001_schema.sql \
  --dry-run=client -o yaml | kubectl apply -f -

echo ">> Construyendo imagenes dentro de Minikube"
minikube image build -t iot-api:1.0 -f api/Dockerfile .
minikube image build -t iot-procesador:1.0 -f processor/Dockerfile .

kubectl apply -f k8s/10_postgres.yaml
kubectl -n "$NS" rollout status deployment/postgres --timeout=240s
kubectl apply -f k8s/20_processor.yaml -f k8s/30_api.yaml
# imagePullPolicy: Never -> reiniciar para que use la imagen recien construida
kubectl -n "$NS" rollout restart deployment/procesador deployment/api
kubectl -n "$NS" rollout status deployment/procesador --timeout=240s
kubectl -n "$NS" rollout status deployment/api --timeout=240s

kubectl -n "$NS" get deployments,pods,svc,pvc
URL="http://$(minikube ip):30080"
printf '\nLISTO. API en: %s\n  Swagger: %s/docs\n  Prueba rapida: curl %s/health/live\n' "$URL" "$URL" "$URL"
printf '  Para los scripts:  export BASE_URL=%s\n' "$URL"

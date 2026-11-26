# Sistema de ingesta y procesamiento de telemetría IoT

Proyecto de **Sistemas Operativos – Segundo Parcial**: evaluación experimental de un sistema distribuido con
Docker, Minikube y Kubernetes.

Simula cientos de dispositivos que envían lecturas (temperatura y consumo eléctrico) a una API REST. Procesadores
replicables validan rangos, calculan promedios móviles, detectan anomalías (z-score) y guardan alertas en PostgreSQL.
Después se mide rendimiento, escalabilidad, recuperación ante fallos e integridad (pruebas E1–E5).

```
k6 (sensores simulados) ──► API FastAPI ──► Service "procesador" ──► Procesador ×1/2/3 ──► PostgreSQL (PVC)
        NodePort :30080       valida formato     balanceo por conexión   valida rangos, promedio       UNIQUE(sensor_id, ts)
                                                                         móvil, z-score, alertas
```

## Reglas de integridad (E5)
1. Una lectura **no se duplica**: `UNIQUE (sensor_id, ts)` + `INSERT … ON CONFLICT DO NOTHING`.
2. Una alerta **no se pierde**: lectura y alerta se guardan en **una sola transacción**, y la API responde `200/201`
   solo **después del `COMMIT`**. Si un pod muere a medias, el cliente no recibe confirmación, reintenta con el mismo
   `(sensor_id, ts)` y no se pierde ni se duplica nada.

## Documentación
| Archivo | Para qué |
|---|---|
| [`docs/GUIA_ENTORNO_WINDOWS.md`](docs/GUIA_ENTORNO_WINDOWS.md) | Preparar WSL 2, Docker, Minikube, k6 y GitHub (paso a paso) |
| [`docs/PLAN_4_DIAS.md`](docs/PLAN_4_DIAS.md) | Qué hace cada día y cada integrante |
| [`docs/ARQUITECTURA.md`](docs/ARQUITECTURA.md) | Diseño, endpoints, modelo de datos, hipótesis |
| [`docs/PROTOCOLO_EXPERIMENTAL.md`](docs/PROTOCOLO_EXPERIMENTAL.md) | Cómo se ejecuta y mide cada prueba |
| [`docs/INFORME_TECNICO_PLANTILLA.md`](docs/INFORME_TECNICO_PLANTILLA.md) | Estructura del informe final |
| [`docs/DEFENSA_INDIVIDUAL.md`](docs/DEFENSA_INDIVIDUAL.md) | Preguntas de práctica para la defensa |

## Inicio rápido (Ubuntu en WSL 2, dentro de `~/`, no en `/mnt/c`)
```bash
bash scripts/setup_wsl.sh          # instala Docker, kubectl, Minikube, k6 (una vez)
bash scripts/verificar_entorno.sh  # comprueba todo

# Configurar contraseña local (solo la primera vez)
cp .env.example .env
nano .env                          # define DB_PASSWORD con una contraseña propia
# Usa una contraseña hexadecimal generada, por ejemplo: openssl rand -hex 32

# 1) Prueba local sin Kubernetes
.venv/bin/python -m pytest -q
docker compose up --build -d       # API en http://localhost:8000/docs
docker compose down

# ADVERTENCIA: usa "docker compose down -v" solo si deseas eliminar
# también los volúmenes y los datos de la base de datos.

# 2) Despliegue real en Minikube
set -a
source .env
set +a
bash scripts/deploy.sh
export BASE_URL=http://$(minikube ip):30080
curl $BASE_URL/health/live

# Si el NodePort no es accesible desde WSL, usa otra terminal:
kubectl port-forward -n telemetria-iot svc/api 18000:8000
# API alternativa: http://127.0.0.1:18000
```

Enviar una lectura de prueba:
```bash
curl -X POST $BASE_URL/api/v1/lecturas -H 'Content-Type: application/json' \
  -d '{"sensor_id":"SENS-0001","ts":"2026-11-19T12:00:00Z","temperatura":95.2,"consumo_w":310}'
# 201 = guardada · repetir el mismo comando → 200 (sin duplicar) · temperatura:999 → 422
curl $BASE_URL/api/v1/alertas
curl $BASE_URL/api/v1/estadisticas
```

## Ejecutar los experimentos
```bash
python3 experiments/ejecutar_experimentos.py --rapido                 # verifica el procedimiento (~8 min)
python3 experiments/ejecutar_experimentos.py --repeticiones 5 --duracion 30s   # corrida oficial (~40-50 min)
python3 experiments/ejecutar_experimentos.py --solo E4 E5             # repetir solo algunos escenarios
.venv/bin/python scripts/graficas.py                                  # gráficas y tablas
bash scripts/capturar_entorno.sh                                      # guarda versiones y recursos del equipo
```
Salidas: `results/resultados_experimentos.csv` (resumen), `results/raw/*.csv.gz` (k6 crudo),
`results/summary/*.json` (k6 + E3/E5), `results/recursos_muestra.csv` (CPU/RAM), `results/plots/*.png`.

## Estructura
```
api/ processor/ shared/     código (FastAPI) · shared/analitica.py = reglas de promedio móvil y alertas
db/init/001_schema.sql      tablas lecturas y alertas con las reglas de integridad
k8s/                        namespace, postgres+PVC, procesador, api (NodePort 30080)
experiments/                k6_telemetria.js, k6_idempotencia.js, ejecutar_experimentos.py
scripts/                    deploy.sh, setup_wsl.sh, verificar_entorno.sh, capturar_entorno.sh, graficas.py
tests/                      unitarias + integración (con PostgreSQL real, opcional)
results/                    datos originales (se versionan: son entregable)
```

## Limitaciones conocidas
- Minikube corre en **un solo equipo**: eliminar un pod modela el fallo de una instancia, **no** la pérdida de un servidor.
- PostgreSQL es una sola instancia (punto único de fallo); E4 elimina procesadores, no la base.
- La API tiene 1 réplica y k6 comparte CPU con el clúster: tres réplicas **pueden no mejorar** el rendimiento. Es un hallazgo válido, no un error.
- Secretos de laboratorio: no exponer esto a Internet.

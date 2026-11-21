# Protocolo experimental E1–E5

## Controles (aplican a todo)
1. Mismo equipo, mismo clúster, mismos límites de recursos. Antes de medir: `bash scripts/capturar_entorno.sh` y anotar qué programas de Windows estaban abiertos (idealmente ninguno pesado).
2. Una variable cambia a la vez. Entre escenarios hay calentamiento de 6 s (no se registra) y 5 s de estabilización al cambiar réplicas.
3. **5 repeticiones** por configuración, **30 s** cada una. Las tablas muestran media y desviación estándar.
4. No se editan los datos crudos (`results/raw/*.csv.gz`, `results/summary/*.json`). Las corridas anómalas se documentan, no se borran.
5. El script vacía las tablas al empezar (`TRUNCATE`) para partir del mismo estado; `--sin-reset-bd` lo evita.

## Escenarios
| Prueba | Configuración | Variable observada | Criterio de éxito |
|---|---|---|---|
| **E1 Línea base** | 1 réplica, 10 VUs | mediana, p95, solicitudes/s, error | referencia repetible (desv. estándar pequeña) |
| **E2 Escalabilidad** | 1, 2 y 3 réplicas, 20 VUs | solicitudes/s, p95, error, CPU | se mide la mejora `((Rₙ−R₁)/R₁)·100`; el resultado puede ser nulo y se explica |
| **E3 Concurrencia** | 2 réplicas, 5/20/50 VUs + 20 VUs con la **misma** lectura | p95, error, filas en BD | idempotencia: exactamente **1 fila y 1 alerta**; se identifica el punto de saturación |
| **E4 Fallo de instancia** | 2 réplicas, 20 VUs, 40 s; a los 8 s se elimina un pod | errores, ventana de errores, tiempo de recuperación | el pod se recrea; se reporta cuántas solicitudes fallaron y cuánto duró |
| **E5 Integridad** | 2 réplicas; 2400 lecturas (20 % críticas) con reintentos mientras se elimina un pod y se hace `rollout restart`; luego se reinicia PostgreSQL | lecturas/alertas perdidas, duplicados, alertas faltantes | todas en **0**; el total de lecturas no cambia tras reiniciar PostgreSQL |

## Métricas
- `solicitudes_por_segundo` (k6 `http_reqs.rate`), `latencia_mediana_ms`, `latencia_p95_ms`.
- `tasa_error_http` (0–1; ×100 = %). `tasa_error_negocio`: proporción de respuestas ≠ 201 en la carga de lecturas nuevas.
- `tiempo_recuperacion_pod_s`: desde `kubectl delete pod` hasta tener de nuevo N pods **Ready**. **No es lo mismo** que la interrupción que vio el cliente.
- `solicitudes_fallidas` y `ventana_errores_s`: calculadas del CSV crudo de k6 (resolución de 1 s) = interrupción percibida.
- CPU y memoria por pod: muestras de `kubectl top pods` cada 5 s (`results/recursos_muestra.csv`). El metrics-server actualiza cada ~15–60 s, así que hay pocas muestras por corrida: úsalas como orden de magnitud y respáldalas con capturas.
- Integridad: ver `results/summary/E3_integridad.json` y `E5_integridad.json`.

## Qué esperar (y qué no tomar por error)
- Mejora de 1→2 réplicas probable; 2→3 dudosa por CPU compartida. Un resultado plano **es válido**.
- Si p95 baja pero los errores suben, no es una mejora real (lo dice el PDF).
- Errores en E4 con 2 réplicas son esperables: las solicitudes que iban hacia el pod eliminado fallan hasta que Kubernetes lo retira del Service.

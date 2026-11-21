# Informe técnico — Sistema de ingesta y procesamiento de telemetría IoT en Kubernetes

**Materia:** Sistemas Operativos – segundo parcial · **Equipo:** [4 nombres] · **Fecha:** [ ] · **Repositorio:** [URL]

> Completa **solo con mediciones reales** (`results/`). Borra los textos entre corchetes al terminar.

## 1. Resumen
[3–5 líneas: qué se construyó, qué se midió y los 2–3 hallazgos principales con números.]

## 2. Problema y objetivos
[Fallos parciales, concurrencia y saturación en sistemas distribuidos. Objetivo general y específicos del PDF.]

## 3. Arquitectura y decisiones de diseño
Ver `docs/ARQUITECTURA.md`. [Diagrama, modelo de datos, reglas de integridad, tabla de decisiones.]

## 4. Entorno de prueba (de `results/entorno.txt`)
| Elemento | Valor |
|---|---|
| CPU / hilos | [i5-1035G1, 4 núcleos / 8 hilos] |
| RAM Windows / WSL | [8 GB / 4 GB] |
| WSL `processors` y `swap` | [ ] |
| Docker / Minikube / Kubernetes / k6 | [versiones] |
| Recursos de Minikube | [3 CPUs, 2800 MB] |
| Duración y repeticiones | [30 s, 5] |
| Programas abiertos durante la medición | [ ] |

## 5. Diseño experimental
[Tabla E1–E5 de `docs/PROTOCOLO_EXPERIMENTAL.md`: objetivo, configuración, duración, carga, variable, criterio de éxito.]

## 6. Resultados
### E1 — Línea base
[`results/analisis_E1.csv`: mediana, p95, solicitudes/s, error (media ± desv. est.)]

### E2 — Escalabilidad
| Réplicas | Solicitudes/s | Mejora vs. 1 | p95 (ms) | Error (%) | CPU total (m) |
|---|---:|---:|---:|---:|---:|
| 1 | [ ] | 0 % | [ ] | [ ] | [ ] |
| 2 | [ ] | [ ] | [ ] | [ ] | [ ] |
| 3 | [ ] | [ ] | [ ] | [ ] | [ ] |

[Gráficas `results/plots/E2_*.png`. ¿La mejora positiva vino acompañada de peor latencia o más errores?]

### E3 — Concurrencia e idempotencia
[`E3_concurrencia.png`, punto de saturación; `E3_integridad.json`: filas = 1, alertas = 1.]

### E4 — Fallo de instancia
[Tiempo de recuperación (s), solicitudes fallidas, ventana de errores, capturas de `kubectl get pods -w`.]

### E5 — Integridad
| Métrica | Valor (debe ser 0) |
|---|---|
| Lecturas perdidas | [ ] |
| Alertas críticas perdidas | [ ] |
| Lecturas duplicadas | [ ] |
| Lecturas críticas sin alerta | [ ] |
| Total de lecturas antes / después de reiniciar PostgreSQL | [ ] / [ ] |

## 7. Análisis y limitaciones
[Contrastar con H1–H6. ¿Qué mejoró, qué empeoró y por qué? Cuello de botella. Limitaciones: un solo equipo, PostgreSQL sin réplica, API ×1, k6 comparte CPU, resolución de metrics-server, número de repeticiones.]

## 8. Conclusiones
[Con números. No afirmar nada sin evidencia.]

## 9. Referencias
Minikube https://minikube.sigs.k8s.io/docs/start/ · Probes https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/ · k6 https://grafana.com/docs/k6/latest/ · Recursos Docker https://docs.docker.com/engine/containers/resource_constraints/

## 10. Evidencias
[Capturas, CSV, gráficas, commit/tag usado.]

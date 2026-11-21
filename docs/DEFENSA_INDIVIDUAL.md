# Guía para la defensa individual

Cada integrante debe: **(1)** explicar la arquitectura completa, **(2)** interpretar al menos una métrica con sus números,
**(3)** mostrar un archivo que modificó y ejecutar un comando en vivo.

1. **¿Qué hace el sistema?** Sensores simulados envían lecturas; la API valida formato; los procesadores validan rangos, calculan promedio móvil/z-score, generan alertas y guardan en PostgreSQL.
2. **¿Por qué es distribuido?** API, procesadores y base son procesos separados que se comunican por red y pueden fallar de forma parcial.
3. **Docker vs Kubernetes.** Docker empaqueta y ejecuta imágenes; Kubernetes gestiona réplicas, Services, probes y recuperación.
4. **¿Qué es un pod, un Deployment, un Service?** Pod: unidad mínima; Deployment: mantiene N réplicas; Service: IP estable que reparte entre pods Ready.
5. **¿Por qué NodePort y no `port-forward`?** `port-forward` fija la conexión a un pod; arruinaría la comparación de réplicas.
6. **¿Por qué la API no usa keep-alive hacia el procesador?** El Service balancea por conexión; con keep-alive los pods nuevos no recibirían tráfico.
7. **¿Cómo evitan duplicados?** `UNIQUE (sensor_id, ts)` + `ON CONFLICT DO NOTHING`; el reintento devuelve 200 sin insertar.
8. **¿Cómo evitan perder alertas críticas?** Lectura y alerta en una transacción y respuesta solo tras COMMIT; si no hay confirmación, el cliente reintenta con la misma clave.
9. **¿Qué pasa si el pod muere a mitad de una escritura?** La transacción hace rollback o ya hizo commit; en ambos casos el reintento idempotente deja el estado correcto.
10. **¿Qué es p95 y por qué no el promedio?** El 95 % de las solicitudes tardó ≤ p95; el promedio oculta colas largas.
11. **¿Por qué 3 réplicas pueden no mejorar?** CPU compartida (clúster + k6 + Windows), 1 réplica de API, `fsync` de PostgreSQL, límites de CPU.
12. **Tiempo de recuperación vs. interrupción percibida.** Lo primero es hasta tener N pods Ready; lo segundo, la ventana en que k6 vio errores.
13. **¿Qué demuestra y qué no demuestra Minikube?** Fallo de instancia sí; pérdida de un servidor físico no.
14. **Fórmula de mejora y tasa de error.** `((Rₙ−R₁)/R₁)·100` solo si R₁>0; errores / totales ×100.
15. **¿Cómo reproducir todo desde cero?** README: `scripts/setup_wsl.sh` → `deploy.sh` → `ejecutar_experimentos.py` → `graficas.py`.

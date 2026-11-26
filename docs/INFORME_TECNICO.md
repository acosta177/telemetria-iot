# Informe técnico — Sistema de ingesta y procesamiento de telemetría IoT en Kubernetes

# INFORME TÉCNICO

**Materia:** Sistemas Operativos – Segundo Parcial
**Equipo:**  Maria Esperanza Acosta Bernal, Daniel Cejudo Cejudo
**Fecha:** 26 de noviembre 2026
**Repositorio:** [https://github.com/acosta177/telemetria-iot.git]

---

## 1. Resumen

Se desarrolló un sistema distribuido de ingesta y procesamiento de telemetría IoT utilizando Docker, Kubernetes mediante Minikube, FastAPI y PostgreSQL. Se evaluaron cinco escenarios experimentales para medir el rendimiento, la escalabilidad,
la concurrencia, la recuperación ante fallos y la integridad de los datos.

Los resultados mostraron que dos réplicas del procesador alcanzaron un rendimiento promedio de 134.54 solicitudes por segundo, con una mejora del 14.42 % respecto a una réplica.
Al incrementar la concurrencia hasta 50 usuarios virtuales, la latencia p95 alcanzó 709.56 ms. Finalmente, la prueba de integridad confirmó que las 2,400 lecturas enviadas fueron almacenadas correctamente,
 sin pérdidas, duplicados ni alertas críticas faltantes, incluso durante la eliminación y reinicialización de pods y el reinicio de PostgreSQL.

## 2. Problema y objetivos

### 2.1 Planteamiento del problema

Los sistemas distribuidos que reciben información de múltiples dispositivos IoT deben garantizar que los datos sean procesados correctamente incluso cuando existen solicitudes simultáneas, fallos parciales de componentes o incrementos en la carga de trabajo.

Entre los principales problemas se encuentran:
- La pérdida de información durante interrupciones de servicios.
- La duplicación de registros debido a reintentos de solicitudes.
- La saturación de recursos al incrementar el número de dispositivos.
- La degradación del rendimiento ante mayores niveles de concurrencia.
- La necesidad de mantener la disponibilidad del procesamiento cuando una instancia falla.

### 2.2 Objetivo general

Implementar y evaluar experimentalmente un sistema distribuido de ingesta y procesamiento de telemetría IoT mediante Docker y Kubernetes, analizando su rendimiento, escalabilidad, recuperación ante fallos e integridad de datos.

### 2.3 Objetivos específicos

- Implementar una API REST para recibir lecturas de sensores.
- Distribuir el procesamiento mediante múltiples réplicas de un servicio.
- Validar rangos físicos de temperatura y consumo eléctrico.
- Calcular promedios móviles y detectar anomalías mediante z-score.
- Almacenar lecturas y alertas en PostgreSQL con restricciones de integridad.
- Evaluar el comportamiento bajo diferentes niveles de concurrencia.
- Comprobar la recuperación de los procesadores ante fallos.
- Verificar la persistencia de los datos después de reiniciar PostgreSQL.

## 3. Arquitectura y decisiones de diseño

El sistema se compone de cuatro elementos principales:

1. **Generador de carga (k6):** simula dispositivos IoT que envían lecturas de temperatura y consumo eléctrico.
2. **API REST (FastAPI):** recibe las solicitudes, valida el formato de los datos y las reenvía al procesador.
3. **Procesadores:** validan rangos físicos, calculan indicadores estadísticos y generan alertas.
4. **Base de datos (PostgreSQL):** almacena las lecturas y alertas utilizando persistencia mediante PersistentVolumeClaim (PVC).

### 3.1 Flujo de procesamiento

k6 → API FastAPI → Service de Kubernetes → Procesadores → PostgreSQL.

El Service distribuye las solicitudes entre las réplicas disponibles del procesador.

### 3.2 Modelo de datos e integridad

Se implementó una restricción UNIQUE sobre la combinación de `sensor_id` y `ts`, evitando que una misma lectura sea almacenada más de una vez.

Las lecturas y sus alertas correspondientes se registran dentro de una misma transacción. La respuesta de confirmación se envía después del COMMIT.

### 3.3 Decisiones de diseño

| Decisión | Justificación |
|---|---|
| Kubernetes y Minikube | Permiten desplegar y administrar los componentes distribuidos. |
| Service NodePort | Permite acceder a la API y distribuir las solicitudes. |
| Múltiples réplicas del procesador | Permiten evaluar la escalabilidad y recuperación. |
| PostgreSQL con PVC | Mantiene la persistencia de los datos. |
| Restricción UNIQUE | Evita duplicados durante los reintentos. |
| Transacciones SQL | Mantienen la consistencia entre lecturas y alertas. |
| Readiness y liveness probes | Permiten comprobar el estado de los contenedores. |
| Límites de CPU y memoria | Controlan los recursos asignados a los pods. |

El diagrama detallado de arquitectura y las decisiones técnicas se encuentran en `docs/ARQUITECTURA.md`.

## 4. Entorno de prueba

Las pruebas se ejecutaron en Ubuntu sobre WSL 2, utilizando Docker y Minikube.

| Elemento | Configuración |
|---|---|
| Procesador | Intel Core i5-1035G1 |
| Núcleos físicos | 4 |
| Procesadores lógicos | 8 |
| RAM física | 7.75 GB |
| Memoria WSL | 4 GB |
| Procesadores WSL | 4 |
| Swap WSL | 2 GB |
| Docker | 29.2.1 |
| Minikube | v1.39.0 |
| kubectl cliente | v1.37.2 |
| Kubernetes servidor | v1.37.0 |
| k6 | v2.4.0 |
| Kernel WSL | 6.18.5.1 |
| Repeticiones | 5 |
| Duración general | 30 segundos por repetición |

**Recursos observados en Minikube:**

- CPU: 4 núcleos reportados.
- Memoria: 4,012,596 KiB de capacidad.
- Sistema operativo del nodo: Debian GNU/Linux 12.

**Programas abiertos durante las mediciones:**

Los datos de configuración se obtuvieron mediante `scripts/capturar_entorno.sh` y los comandos de PowerShell utilizados para consultar las características físicas del equipo.

## 5. Diseño experimental

Se realizaron cinco pruebas experimentales siguiendo el protocolo definido en `docs/PROTOCOLO_EXPERIMENTAL.md`.

| Prueba | Objetivo | Configuración | Variable principal |
|---|---|---|---|
| E1 | Línea base | 1 réplica, 10 VUs | Rendimiento y latencia |
| E2 | Escalabilidad | 1, 2 y 3 réplicas, 20 VUs | Solicitudes/s, CPU y p95 |
| E3 | Concurrencia | 2 réplicas, 5, 20 y 50 VUs | Latencia y errores |
| E4 | Recuperación | 2 réplicas, 20 VUs, eliminación de un pod | Tiempo de recuperación y solicitudes fallidas |
| E5 | Integridad | 2 réplicas y 2,400 lecturas | Pérdidas, duplicados y persistencia |

Las pruebas E1, E2, E3 y E4 se realizaron con cinco repeticiones. E5 se ejecutó como una prueba de integridad con 2,400 lecturas.

Se mantuvo el mismo entorno de ejecución y se registraron las mediciones originales en archivos CSV y JSON.

## 6. Resultados experimentales

### 6.1 E1 — Línea base

Se estableció una referencia de rendimiento utilizando una réplica del procesador y diez usuarios virtuales.

| Métrica | Resultado |
|---|---:|
| Solicitudes por segundo | 96.76 ± 11.74 |
| Latencia mediana | 91.82 ms |
| Latencia p95 | 189.71 ± 31.34 ms |
| Tasa de errores HTTP | 0 % |

**Análisis:**

El sistema procesó las solicitudes sin errores HTTP durante las cinco repeticiones. El rendimiento promedio fue de aproximadamente 96.76 solicitudes por segundo.

Esta medición constituye la referencia para comparar los resultados de escalabilidad y concurrencia.

Fuente: `results/analisis_E1.csv`.

### 6.2 E2 — Escalabilidad

Se evaluó el comportamiento del sistema utilizando una, dos y tres réplicas del procesador, manteniendo veinte usuarios virtuales.

| Réplicas | Solicitudes/s | Mejora vs. 1 | p95 (ms) | Error (%) | CPU total (m) |
|---:|---:|---:|---:|---:|---:|
| 1 | 117.58 | 0 % | 268.61 | 0 | 464.87 |
| 2 | 134.54 | 14.42 % | 278.47 | 0 | 632.84 |
| 3 | 121.82 | 3.60 % | 325.12 | 0 | 574.41 |

**Análisis:**

La configuración de dos réplicas obtuvo el mayor rendimiento, con 134.54 solicitudes por segundo, lo que representa una mejora del 14.42 % respecto a una réplica.

Al utilizar tres réplicas, el rendimiento disminuyó a 121.82 solicitudes por segundo. Esto representa una reducción aproximada del 9.46 % respecto a dos réplicas.

Aunque aumentar el número de instancias puede incrementar la capacidad de procesamiento, los resultados muestran que los recursos compartidos del equipo limitan el beneficio de agregar más réplicas.

No se registraron errores HTTP en ninguna de las configuraciones.

**Gráficas:**
- `results/plots/E2_rendimiento.png`
- `results/plots/E2_latencia_p95.png`
- `results/plots/E2_errores.png`
- `results/plots/E2_cpu.png`

### 6.3 E3 — Concurrencia e idempotencia

Se evaluó el comportamiento del sistema con dos réplicas del procesador y diferentes cantidades de usuarios virtuales.

| Usuarios virtuales | Solicitudes/s | Latencia mediana (ms) | p95 (ms) | Error HTTP |
|---:|---:|---:|---:|---:|
| 5 | 119.76 | 36.99 | 86.11 | 0 % |
| 20 | 123.79 | 133.52 | 485.29 | 0 % |
| 50 | 117.24 | 425.02 | 709.56 | 0 % |

**Análisis:**

Con cinco usuarios virtuales se obtuvo la menor latencia, con un p95 de 86.11 ms.

Al incrementar la concurrencia a veinte usuarios, la latencia p95 aumentó a 485.29 ms. Con cincuenta usuarios alcanzó 709.56 ms.

El rendimiento no aumentó proporcionalmente al número de usuarios, mientras que la latencia creció considerablemente.

Esto muestra una degradación del rendimiento al aumentar la concurrencia y sugiere que el sistema se aproxima a su límite de capacidad en las condiciones de prueba.

**Prueba de idempotencia:**

Se enviaron solicitudes concurrentes correspondientes a una misma lectura, utilizando el mismo identificador de sensor y marca temporal.

Resultado:

- Filas en la tabla `lecturas`: 1.
- Filas en la tabla `alertas`: 1.
- Regla de integridad: válida.

La prueba confirmó que los reintentos concurrentes no generaron registros duplicados ni alertas adicionales.

Fuente: `results/summary/E3_integridad.json`.

Gráfica: `results/plots/E3_concurrencia.png`.

### 6.4 E4 — Recuperación ante fallos

Se eliminó una instancia del procesador mientras se mantenía una carga de veinte usuarios virtuales y dos réplicas configuradas.

| Repetición | Recuperación del pod (s) | Solicitudes fallidas | Ventana de errores (s) |
|---:|---:|---:|---:|
| 1 | 12.862 | 13 | 2 |
| 2 | 9.956 | 16 | 2 |
| 3 | 17.037 | 2 | 1 |
| 4 | 9.706 | 7 | 30 |
| 5 | 9.851 | 10 | 1 |

**Resultados generales:**

- Tiempo promedio de recuperación: 11.88 segundos.
- Solicitudes fallidas acumuladas: 48.
- Promedio de solicitudes fallidas por repetición: 9.6.
- Ventana mediana de errores: 2 segundos.
- Tasa de errores HTTP: variable según la repetición.

**Análisis:**

Kubernetes permitió recrear los pods eliminados y recuperar el número configurado de réplicas.

Durante la eliminación se registraron solicitudes fallidas, lo que demuestra que la recuperación automática de una instancia no implica que todas las solicitudes sean atendidas sin interrupciones.

La cuarta repetición presentó una ventana de errores de 30 segundos, considerablemente superior a las demás. Este resultado debe conservarse y considerarse al interpretar la variabilidad experimental.

Es importante distinguir entre el tiempo que tarda Kubernetes en recuperar el pod y el tiempo durante el cual los clientes experimentan errores.

Gráfica: `results/plots/E4_recuperacion.png`.

### 6.5 E5 — Integridad y persistencia

Se enviaron 2,400 lecturas, incluyendo 480 lecturas críticas, mientras se provocaban fallos mediante la eliminación de un pod y el reinicio del deployment del procesador.

| Métrica | Resultado |
|---|---:|
| Lecturas enviadas | 2,400 |
| Lecturas confirmadas | 2,400 |
| Lecturas almacenadas | 2,400 |
| Lecturas perdidas | 0 |
| Lecturas duplicadas | 0 |
| Alertas críticas confirmadas | 480 |
| Alertas críticas almacenadas | 480 |
| Alertas críticas perdidas | 0 |
| Lecturas con alerta faltante | 0 |
| Reintentos por errores transitorios | 27 |
| Solicitudes sin confirmar tras 20 intentos | 0 |

**Verificación de persistencia de PostgreSQL:**

| Comprobación | Total |
|---|---:|
| Lecturas antes del reinicio | 138,082 |
| Lecturas después del reinicio | 138,082 |

**Análisis:**

Los resultados muestran que todas las lecturas confirmadas fueron almacenadas correctamente. No se detectaron pérdidas ni duplicados.

Asimismo, las 480 alertas críticas fueron registradas y ninguna lectura crítica quedó sin su alerta correspondiente.

Durante el experimento se necesitaron 27 reintentos por errores transitorios. Sin embargo, todas las lecturas terminaron confirmándose.

Después del reinicio de PostgreSQL, el total de registros permaneció en 138,082, lo que demuestra la persistencia de los datos en el volumen utilizado.

**Resultado:** integridad y persistencia verificadas en las condiciones de esta prueba.

Fuente: `results/summary/E5_integridad.json`.

## 7. Análisis y limitaciones

### 7.1 Contraste de hipótesis

| Hipótesis | Resultado | Interpretación |
|---|---|---|
| H1: aumentar las réplicas mejora el rendimiento mientras el procesador sea el límite | Parcialmente respaldada | Dos réplicas mejoraron el rendimiento 14.42 %, pero tres no superaron a dos. |
| H2: aumentar la concurrencia incrementa la latencia y los errores | Parcialmente respaldada | La latencia aumentó considerablemente, pero no se registraron errores HTTP en E3. |
| H3: Kubernetes recupera los pods después de su eliminación | Respaldada | Los pods fueron recreados, aunque se presentaron solicitudes fallidas. |
| H4: no se pierden lecturas ni alertas confirmadas después de reinicios | Respaldada | E5 registró cero pérdidas y verificó la persistencia de PostgreSQL. |
| H5: solicitudes concurrentes con la misma lectura producen un solo registro y una alerta | Respaldada | Se verificó una fila en lecturas y una en alertas. |
| H6: tres réplicas pueden no mejorar frente a dos | Respaldada | El rendimiento de tres réplicas fue inferior al de dos. |

### 7.2 Cuellos de botella

Los resultados permiten identificar una limitación de rendimiento cuando se incrementa la concurrencia.

La latencia p95 pasó de 86.11 ms con cinco usuarios virtuales a 709.56 ms con cincuenta.

También se observó que incrementar las réplicas no garantiza una mejora proporcional, debido a que los componentes comparten recursos de CPU y memoria.

La API se mantuvo con una sola réplica y PostgreSQL utilizó una única instancia, por lo que ambos componentes representan posibles limitaciones de escalabilidad.

### 7.3 Limitaciones experimentales

- El clúster Minikube se ejecutó en un solo equipo físico.
- PostgreSQL utilizó una sola instancia, sin replicación.
- La API se mantuvo con una sola réplica.
- El generador k6 compartió recursos con el clúster.
- Las mediciones de CPU y memoria mediante metrics-server tienen una resolución limitada.
- Los resultados representan las condiciones particulares del equipo utilizado.
- Las pruebas de recuperación se enfocaron en la eliminación de pods, no en la pérdida del servidor físico.
- La persistencia de PostgreSQL se verificó mediante reinicio de su pod, no mediante un fallo del almacenamiento físico.

## 8. Conclusiones

El proyecto permitió implementar y evaluar un sistema distribuido de procesamiento de telemetría IoT utilizando Docker, Kubernetes, FastAPI y PostgreSQL.

Los resultados experimentales permitieron identificar que la configuración con dos réplicas obtuvo el mejor rendimiento promedio, alcanzando 134.54 solicitudes por segundo y una mejora del 14.42 % respecto a una réplica.

La prueba de concurrencia mostró que el incremento de usuarios virtuales provoca un aumento significativo de la latencia, alcanzando un p95 de 709.56 ms con cincuenta usuarios.

En cuanto a la recuperación, Kubernetes logró recrear las instancias eliminadas, aunque durante el proceso se registraron solicitudes fallidas.

Finalmente, E5 confirmó la integridad de la información bajo las condiciones evaluadas: las 2,400 lecturas fueron almacenadas, las 480 alertas críticas se conservaron y no se detectaron pérdidas ni duplicados.
 También se verificó que PostgreSQL mantuvo los 138,082 registros después de reiniciar su pod.

En conclusión, el sistema cumplió los objetivos experimentales de rendimiento, escalabilidad, recuperación e integridad planteados para el proyecto, dentro de las limitaciones del entorno de laboratorio.

## 9. Referencias

1. Minikube. Documentación oficial. https://minikube.sigs.k8s.io/docs/start/
2. Kubernetes. Configure Liveness, Readiness and Startup Probes. https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/
3. Grafana. k6 Documentation. https://grafana.com/docs/k6/latest/
4. Docker. Resource Constraints. https://docs.docker.com/engine/containers/resource_constraints/

## 10. Evidencias

Las evidencias experimentales se encuentran organizadas dentro del directorio `results/`.

| Evidencia | Ubicación |
|---|---|
| Resultados generales | `results/resultados_experimentos.csv` |
| Resultados originales de k6 | `results/raw/` |
| Resúmenes de experimentos | `results/summary/` |
| Resultados estadísticos E1 | `results/analisis_E1.csv` |
| Resultados estadísticos E2 | `results/analisis_escalabilidad.csv` |
| Resultados estadísticos E3 | `results/analisis_concurrencia.csv` |
| Resultados estadísticos E4 | `results/analisis_E4.csv` |
| Uso de recursos | `results/analisis_recursos.csv` |
| Registro del entorno | `results/entorno.txt` |
| Gráficas experimentales | `results/plots/` |
| Evidencias adicionales | `evidencias/` |

**Commit de referencia:** `33706a5` (registrado durante la captura del entorno).

**Repositorio:** [https://github.com/acosta177/telemetria-iot.git].

**Integrantes:** [Maria Esperanza Acosta Bernal, Daniel Cejudo Cejudo].

# Plan de 4 días

Roles (los del PDF). **Todos** revisan código, participan en una prueba de integración y defienden todo el sistema.

| Rol | Responsable principal de |
|---|---|
| 1. Infraestructura | `k8s/`, `scripts/deploy.sh`, Docker, Minikube |
| 2. Aplicación y datos | `api/`, `processor/`, `shared/`, `db/` |
| 3. Pruebas y rendimiento | `experiments/`, `scripts/graficas.py`, datos y gráficas |
| 4. Fallos, consistencia e integración | E4/E5, informe, README, revisión de PRs |

Cada integrante abre **al menos un Pull Request** con algo propio (así hay evidencia individual).

## Día 1 — Entorno y primer despliegue
**Todos (mañana):** `docs/GUIA_ENTORNO_WINDOWS.md` pasos 1–6 en el equipo de medición; los demás, `git clone`, `pytest` y `docker compose`.
**Administrador:** sube el repo a GitHub, agrega colaboradores y protege `main` (guía, sección 7).

| Quién | Tarea | Listo cuando |
|---|---|---|
| 1 | `bash scripts/deploy.sh` y `kubectl get pods` | 3 pods `Running` |
| 2 | Leer `processor/main.py` y `shared/analitica.py`; correr `pytest` | tests en verde |
| 3 | Instalar k6; corrida corta: `python3 experiments/ejecutar_experimentos.py --rapido --solo E1` | aparece `results/resultados_experimentos.csv` |
| 4 | Redactar `docs/ARQUITECTURA.md` (ya hay base) con sus palabras; probar `curl` de la guía | diseño revisado |

**Entregable:** diseño breve + sistema desplegado en Minikube + 1 PR por persona.
**Commit de cierre:** `git commit -m "chore: dia 1 entorno y despliegue"`.

## Día 2 — Comprensión y pruebas piloto
1. Cada quien explica a los demás su módulo (15 min c/u). Es práctica de la defensa.
2. Corrida piloto completa: `python3 experiments/ejecutar_experimentos.py --rapido` (~8 min). Revisar `results/summary/*.log` y `results/resultados_experimentos.csv`.
3. Ajustar si hace falta (rol 3): si con 1 réplica ya hay errores, bajar VUs; si con 3 no se satura nada, subir VUs en `ejecutar_experimentos.py`. Anotar el motivo en el informe.
4. Rol 4: ensayar a mano E4 y E5 (`kubectl delete pod …` mientras corre `k6`) para entender lo que mide el script.
5. Rol 2: probar casos límite con `curl` (422, 409, reintento 200) y dejar tests nuevos si encuentra algo.

**Entregable:** pipeline de medición validado, hipótesis escritas (ARQUITECTURA.md §6), PRs integrados.

## Día 3 — Mediciones oficiales
Antes de empezar (rol 3 y 1): cerrar todo lo pesado en Windows, `bash scripts/capturar_entorno.sh`, anotar a mano qué estaba abierto.
```bash
python3 experiments/ejecutar_experimentos.py --repeticiones 5 --duracion 30s     # ~40-50 min, no tocar el equipo
.venv/bin/python scripts/graficas.py
```
- Si un escenario sale raro (ruido de Windows), repetirlo solo: `--solo E2` (no borres los datos malos: documéntalos).
- Tomar capturas de `kubectl get pods -w`, `kubectl top pods` y `kubectl get events` durante E4.
- Commit de `results/` (son entregable): `git add results && git commit -m "data: mediciones oficiales"`.

**Entregable:** CSV originales, gráficas preliminares, registro del entorno.

## Día 4 — Análisis, informe y reproducibilidad
1. **Análisis (todos):** completar `docs/INFORME_TECNICO_PLANTILLA.md` con números reales. Preguntas guía: ¿mejoró el rendimiento con 2 y 3 réplicas? ¿qué empeoró (latencia, errores)? ¿quién es el cuello de botella (CPU, PostgreSQL, API, k6)? ¿qué pasó en E4? ¿E5 dio 0 pérdidas y 0 duplicados?
2. **Reproducibilidad (rol 1):** en un clon limpio: `minikube delete`, seguir el README desde cero, comprobar que funciona.
3. **Documento de diseño en PDF:** `pandoc docs/ARQUITECTURA.md -o docs/Documento_diseno_y_arquitectura.pdf` (o exportar desde el editor).
4. **Ensayo de defensa:** `docs/DEFENSA_INDIVIDUAL.md`; cada quien muestra un archivo suyo, un comando y una métrica.
5. Etiqueta final: `git tag v1.0 && git push --tags`.

**Entregables del PDF cubiertos:** diseño, repositorio, manual, scripts de prueba, CSV, gráficas, informe, demo.

## Si te quedas sin tiempo (prioridad)
1. E1, E2 y E5 completos con 5 repeticiones. 2. E4. 3. E3. Nunca inventes datos: un escenario con 3 repeticiones reales vale más que 5 dudosas; dilo en el informe.

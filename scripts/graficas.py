#!/usr/bin/env python3
"""Genera graficas y tablas a partir de los CSV reales. Requiere: pip install pandas matplotlib."""
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd

root = Path(__file__).resolve().parents[1]
ruta = root / 'results/resultados_experimentos.csv'
if not ruta.exists():
    raise SystemExit('No hay datos reales: ejecuta experiments/ejecutar_experimentos.py primero.')
salida = root / 'results/plots'
salida.mkdir(exist_ok=True, parents=True)

df = pd.read_csv(ruta)
for c in ('solicitudes_por_segundo', 'latencia_mediana_ms', 'latencia_p95_ms', 'tasa_error_http',
          'tasa_error_negocio', 'tiempo_recuperacion_pod_s', 'ventana_errores_s', 'solicitudes_fallidas'):
    if c in df:
        df[c] = pd.to_numeric(df[c], errors='coerce')


def linea(ax, x, y, err=None, **kw):
    ax.errorbar(x, y, yerr=err, marker='o', capsize=4, **kw)


def guardar(fig, nombre):
    fig.tight_layout()
    fig.savefig(salida / nombre, dpi=150)
    plt.close(fig)


# ---- Tablas resumen (media y desviacion estandar) ----
def resumen(esc, por):
    d = df[df.escenario == esc]
    if d.empty:
        return pd.DataFrame()
    g = d.groupby(por).agg(
        n=('repeticion', 'count'),
        rps=('solicitudes_por_segundo', 'mean'), rps_sd=('solicitudes_por_segundo', 'std'),
        mediana_ms=('latencia_mediana_ms', 'mean'),
        p95_ms=('latencia_p95_ms', 'mean'), p95_sd=('latencia_p95_ms', 'std'),
        error_http_pct=('tasa_error_http', lambda s: s.mean() * 100)).reset_index()
    return g.fillna(0)


# ---- E1 ----
e1 = resumen('E1_base', 'replicas')
if not e1.empty:
    e1.to_csv(root / 'results/analisis_E1.csv', index=False)

# ---- E2: escalabilidad ----
e2 = resumen('E2_escalabilidad', 'replicas')
if not e2.empty:
    r1 = e2.loc[e2.replicas == 1, 'rps']
    base = float(r1.iloc[0]) if len(r1) else 0.0
    # Mejora (%) = ((Rn - R1) / R1) * 100, solo si R1 > 0 (formula del PDF)
    e2['mejora_pct'] = ((e2.rps - base) / base * 100) if base > 0 else float('nan')
    e2.to_csv(root / 'results/analisis_escalabilidad.csv', index=False)
    for col, sd, titulo, y, nombre in [
        ('rps', 'rps_sd', 'E2: rendimiento vs. replicas del procesador', 'solicitudes/s', 'E2_rendimiento.png'),
        ('p95_ms', 'p95_sd', 'E2: latencia p95 vs. replicas', 'p95 (ms)', 'E2_latencia_p95.png'),
        ('error_http_pct', None, 'E2: tasa de error HTTP vs. replicas', 'error (%)', 'E2_errores.png'),
    ]:
        fig, ax = plt.subplots(figsize=(6.5, 4))
        linea(ax, e2.replicas, e2[col], e2[sd] if sd else None)
        ax.set(xlabel='Replicas del procesador', ylabel=y, title=titulo, xticks=[1, 2, 3])
        ax.grid(alpha=.3)
        guardar(fig, nombre)

# ---- E3: concurrencia ----
e3 = resumen('E3_concurrencia', 'vus')
if not e3.empty:
    e3.to_csv(root / 'results/analisis_concurrencia.csv', index=False)
    fig, ax1 = plt.subplots(figsize=(6.8, 4))
    linea(ax1, e3.vus, e3.p95_ms, e3.p95_sd, color='tab:red', label='p95 (ms)')
    ax1.set(xlabel='Clientes virtuales simultaneos', ylabel='p95 (ms)', title='E3: saturacion bajo concurrencia')
    ax2 = ax1.twinx()
    linea(ax2, e3.vus, e3.rps, e3.rps_sd, color='tab:blue', label='solicitudes/s')
    ax2.set_ylabel('solicitudes/s')
    ax1.grid(alpha=.3)
    guardar(fig, 'E3_concurrencia.png')

# ---- E4: fallo de instancia ----
e4 = df[df.escenario == 'E4_fallo_pod']
if not e4.empty:
    t = e4[['repeticion', 'tiempo_recuperacion_pod_s', 'solicitudes_fallidas', 'ventana_errores_s', 'tasa_error_http']]
    t.to_csv(root / 'results/analisis_E4.csv', index=False)
    fig, ax = plt.subplots(figsize=(6.5, 4))
    ax.bar(e4.repeticion.astype(str), e4.tiempo_recuperacion_pod_s)
    ax.set(xlabel='Repeticion', ylabel='segundos', title='E4: tiempo hasta recuperar las replicas Ready')
    ax.grid(axis='y', alpha=.3)
    guardar(fig, 'E4_recuperacion.png')

# ---- Recursos (CPU/memoria de los procesadores) ----
rec_ruta = root / 'results/recursos_muestra.csv'
if rec_ruta.exists():
    r = pd.read_csv(rec_ruta)
    r['cpu_millicores'] = pd.to_numeric(r['cpu_millicores'], errors='coerce')
    r['memoria_mib'] = pd.to_numeric(r['memoria_mib'], errors='coerce')
    p = r[r.pod.astype(str).str.startswith('procesador')].dropna(subset=['cpu_millicores'])
    if not p.empty:
        por_instante = p.groupby(['escenario', 'replicas', 'instante_utc']).agg(
            cpu_total=('cpu_millicores', 'sum'), mem_total=('memoria_mib', 'sum')).reset_index()
        res = por_instante.groupby(['escenario', 'replicas']).agg(
            cpu_total_prom_m=('cpu_total', 'mean'), mem_total_prom_mib=('mem_total', 'mean')).reset_index()
        res.to_csv(root / 'results/analisis_recursos.csv', index=False)
        e2r = res[res.escenario == 'E2_escalabilidad']
        if not e2r.empty:
            fig, ax = plt.subplots(figsize=(6.5, 4))
            ax.bar(e2r.replicas.astype(str), e2r.cpu_total_prom_m)
            ax.set(xlabel='Replicas del procesador', ylabel='CPU total de procesadores (millicores)',
                   title='E2: CPU consumida por los procesadores')
            ax.grid(axis='y', alpha=.3)
            guardar(fig, 'E2_cpu.png')

print('Graficas y tablas creadas en', salida, 'y results/analisis_*.csv')

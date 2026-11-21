#!/usr/bin/env python3
"""Ejecuta E1-E5 con datos reales (nada simulado). Solo usa la libreria estandar.

Requisitos: Minikube desplegado (scripts/deploy.sh), k6 y kubectl instalados.
Resultados: results/resultados_experimentos.csv, results/raw/*.csv.gz,
            results/summary/*.json|log, results/recursos_muestra.csv
"""
import argparse
import csv
import gzip
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
RAW, SUMMARY = ROOT / 'results/raw', ROOT / 'results/summary'
RESOURCE_CSV = ROOT / 'results/recursos_muestra.csv'
NS = 'telemetria-iot'
PG = ['kubectl', '-n', NS, 'exec', 'deployment/postgres', '--', 'psql', '-U', 'iotuser', '-d', 'telemetria', '-tAc']


def cmd(args, check=True):
    p = subprocess.run(args, text=True, capture_output=True, check=False)
    if check and p.returncode != 0:
        raise RuntimeError(f"Comando fallido: {' '.join(args)}\n{p.stdout}\n{p.stderr}")
    return p


def base_url():
    if os.environ.get('BASE_URL'):
        return os.environ['BASE_URL'].rstrip('/')
    ip = cmd(['minikube', 'ip']).stdout.strip()
    return f'http://{ip}:30080'


BASE = ''


def http_json(metodo, ruta, cuerpo=None, timeout=5):
    """Devuelve (codigo_http, json). (None, None) si no hubo respuesta."""
    data = json.dumps(cuerpo).encode() if cuerpo is not None else None
    req = Request(BASE + ruta, data=data, method=metodo, headers={'Content-Type': 'application/json'})
    try:
        with urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read())
    except HTTPError as e:
        try:
            return e.code, json.loads(e.read())
        except ValueError:
            return e.code, None
    except (URLError, TimeoutError, ConnectionError, OSError, ValueError):
        return None, None


def sql(consulta):
    return cmd(PG + [consulta]).stdout.strip()


# ---------------------------------------------------------------- recursos

class Muestreador(threading.Thread):
    """Toma muestras de `kubectl top pods` cada 5 s mientras corre una prueba."""

    def __init__(self, escenario, replicas, vus):
        super().__init__(daemon=True)
        self.meta = (escenario, replicas, vus)
        self.parar = threading.Event()

    def run(self):
        while not self.parar.is_set():
            self.muestra()
            self.parar.wait(5)

    def muestra(self):
        esc, rep, vus = self.meta
        salida = cmd(['kubectl', '-n', NS, 'top', 'pods', '--no-headers'], check=False)
        ahora = datetime.now(timezone.utc).isoformat()
        filas = []
        if salida.returncode != 0:
            filas.append([esc, rep, vus, ahora, '', '', '', 'metrics-server sin datos'])
        else:
            for linea in salida.stdout.splitlines():
                c = linea.split()
                if len(c) < 3:
                    continue
                cpu = c[1][:-1] if c[1].endswith('m') else str(int(float(c[1]) * 1000))
                mem = c[2]
                mem = mem[:-2] if mem.endswith('Mi') else (str(float(mem[:-2]) * 1024) if mem.endswith('Gi')
                                                            else str(float(mem[:-2]) / 1024) if mem.endswith('Ki') else mem)
                filas.append([esc, rep, vus, ahora, c[0], cpu, mem, ''])
        with RESOURCE_CSV.open('a', newline='', encoding='utf-8') as f:
            csv.writer(f).writerows(filas)


# ---------------------------------------------------------------- utilidades k8s

def pods_procesador():
    j = json.loads(cmd(['kubectl', '-n', NS, 'get', 'pods', '-l', 'app=procesador', '-o', 'json']).stdout)
    return j['items']


def esta_listo(p):
    if p['metadata'].get('deletionTimestamp'):
        return False
    return any(c.get('type') == 'Ready' and c.get('status') == 'True' for c in p.get('status', {}).get('conditions', []))


def esperar_listos(n, excluir=(), timeout=180):
    """Segundos hasta tener `n` pods de procesador Ready (sin contar los de `excluir`)."""
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        if len([p for p in pods_procesador() if esta_listo(p) and p['metadata']['name'] not in excluir]) >= n:
            return round(time.monotonic() - t0, 3)
        time.sleep(0.5)
    return None


def set_replicas(n):
    cmd(['kubectl', '-n', NS, 'scale', 'deployment/procesador', f'--replicas={n}'])
    cmd(['kubectl', '-n', NS, 'rollout', 'status', 'deployment/procesador', '--timeout=180s'])
    esperar_listos(n)
    time.sleep(5)  # estabilizacion (queda documentada en el protocolo)


def calentar(vus=5, segundos=6):
    """Calentamiento (no se registra): evita medir arranques en frio de Python/BD."""
    env = {**os.environ, 'VUS': str(vus), 'DURATION': f'{segundos}s', 'BASE_URL': BASE}
    subprocess.run(['k6', 'run', '--quiet', str(ROOT / 'experiments/k6_telemetria.js')],
                   env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)


# ---------------------------------------------------------------- k6

def metric(j, nombre, campo='value'):
    return j.get('metrics', {}).get(nombre, {}).get('values', {}).get(campo, '')


def analizar_errores_csv(ruta):
    """Del CSV crudo de k6: cuantas solicitudes fallaron y entre que segundos (ventana de interrupcion)."""
    fallos, primero, ultimo = 0, None, None
    with gzip.open(ruta, 'rt', encoding='utf-8', newline='') as f:
        for fila in csv.DictReader(f):
            if fila.get('metric_name') == 'http_req_failed' and float(fila.get('metric_value') or 0) == 1.0:
                t = int(float(fila['timestamp']))
                fallos += 1
                primero = t if primero is None else min(primero, t)
                ultimo = t if ultimo is None else max(ultimo, t)
    ventana = (ultimo - primero + 1) if fallos else 0  # resolucion de 1 s (timestamp de k6)
    return fallos, ventana


def run_k6(escenario, replicas, vus, duracion, repeticion, script='k6_telemetria.js', extra=None,
           inyectar_fallo=False):
    clave = f'{escenario}_r{replicas}_vu{vus}_rep{repeticion}'
    csv_gz = RAW / f'{clave}.csv.gz'
    resumen = SUMMARY / f'{clave}.json'
    log = SUMMARY / f'{clave}.log'
    env = {**os.environ, 'VUS': str(vus), 'DURATION': duracion, 'BASE_URL': BASE,
           'SUMMARY_FILE': str(resumen), 'ESCENARIO': escenario, **(extra or {})}
    args = ['k6', 'run', '--out', f'csv={csv_gz}', str(ROOT / 'experiments' / script)]
    recuperacion, pod_eliminado = '', ''
    muestreo = Muestreador(escenario, replicas, vus)
    with log.open('w', encoding='utf-8') as f:
        proc = subprocess.Popen(args, env=env, stdout=f, stderr=subprocess.STDOUT)
        muestreo.start()
        if inyectar_fallo:
            time.sleep(8)
            nombres = [p['metadata']['name'] for p in pods_procesador()]
            if not nombres:
                proc.terminate()
                raise RuntimeError('No hay pods de procesador que eliminar')
            pod_eliminado = nombres[0]
            t0 = time.monotonic()
            cmd(['kubectl', '-n', NS, 'delete', 'pod', pod_eliminado, '--wait=false'])
            print(f'    E4: pod eliminado: {pod_eliminado}')
            seg = esperar_listos(replicas, excluir=(pod_eliminado,))
            recuperacion = round(time.monotonic() - t0, 3) if seg is not None else ''
        codigo = proc.wait()
        muestreo.parar.set()
        muestreo.join(timeout=10)
    if codigo != 0:
        print(f'    AVISO: k6 devolvio codigo {codigo}; ver {log.name}')
    if not resumen.exists():
        raise RuntimeError(f'No se encontro el resumen de k6: {resumen}. Revisar {log}')
    j = json.loads(resumen.read_text(encoding='utf-8'))
    fallos, ventana = analizar_errores_csv(csv_gz) if csv_gz.exists() else ('', '')
    return {
        'escenario': escenario, 'replicas': replicas, 'vus': vus, 'duracion_configurada': duracion,
        'repeticion': repeticion,
        'solicitudes_por_segundo': metric(j, 'http_reqs', 'rate'),
        'latencia_mediana_ms': metric(j, 'http_req_duration', 'med'),
        'latencia_p95_ms': metric(j, 'http_req_duration', 'p(95)'),
        'tasa_error_http': metric(j, 'http_req_failed', 'rate'),
        'tasa_error_negocio': metric(j, 'errores_negocio', 'rate'),
        'lecturas_creadas': metric(j, 'lecturas_creadas', 'count'),
        'alertas_criticas_confirmadas': metric(j, 'alertas_criticas_confirmadas', 'count'),
        'solicitudes_fallidas': fallos, 'ventana_errores_s': ventana,
        'tiempo_recuperacion_pod_s': recuperacion, 'pod_eliminado': pod_eliminado,
        'csv_crudo': str(csv_gz.relative_to(ROOT)), 'resumen_json': str(resumen.relative_to(ROOT)),
    }


# ---------------------------------------------------------------- E3 idempotencia

def e3_idempotencia(duracion):
    sensor = f'IDEMP-{uuid.uuid4().hex[:8]}'
    ts = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000000Z')
    fila = run_k6('E3_idempotencia', 2, 20, duracion, 1, 'k6_idempotencia.js',
                  {'SENSOR_ID': sensor, 'TS': ts})
    lecturas = int(sql(f"SELECT count(*) FROM lecturas WHERE sensor_id='{sensor}' AND ts='{ts}'::timestamptz"))
    alertas = int(sql(f"SELECT count(*) FROM alertas WHERE sensor_id='{sensor}' AND ts='{ts}'::timestamptz"))
    ok = lecturas == 1 and alertas == 1
    (SUMMARY / 'E3_integridad.json').write_text(json.dumps({
        'sensor_id': sensor, 'ts': ts, 'filas_en_lecturas': lecturas, 'filas_en_alertas': alertas,
        'regla_valida': ok}, indent=2), encoding='utf-8')
    print(f'    E3 idempotencia: lecturas={lecturas} alertas={alertas} -> {"OK" if ok else "VIOLADA"}')
    return fila, ok


# ---------------------------------------------------------------- E5 integridad

def e5_integridad(total=2400, hilos=8, pausa=0.04):
    """Envia lecturas con reintentos mientras se eliminan y reinician pods; verifica en PostgreSQL
    que no se perdio ninguna lectura/alerta confirmada y que no hay duplicados."""
    prefijo = f'E5-{uuid.uuid4().hex[:6]}'
    base_ts = datetime.now(timezone.utc)
    lecturas = []
    for i in range(total):
        critica = (i % 5 == 0)  # 20 % criticas: la regla "no perder alertas criticas" se ejerce mucho
        lecturas.append({
            'sensor_id': f'{prefijo}-{i % 25:03d}',
            'ts': (base_ts + timedelta(microseconds=i)).strftime('%Y-%m-%dT%H:%M:%S.%fZ'),
            'temperatura': 95.0 if critica else round(24 + (i % 7) * 0.4, 2),
            'consumo_w': 300.0})
    confirmadas, criticas_conf, estado = {}, set(), {'reintentos': 0, 'sin_confirmar': 0}
    lock = threading.Lock()

    def enviar(lect):
        time.sleep(pausa)
        for intento in range(20):
            codigo, cuerpo = http_json('POST', '/api/v1/lecturas', lect, timeout=6)
            if codigo in (200, 201):
                with lock:
                    clave = (lect['sensor_id'], lect['ts'])
                    confirmadas[clave] = codigo
                    if cuerpo and cuerpo.get('alerta') and cuerpo['alerta']['severidad'] == 'CRITICA':
                        criticas_conf.add(clave)
                return
            with lock:
                estado['reintentos'] += 1
            time.sleep(0.3)  # mismo (sensor_id, ts): el reintento es idempotente
        with lock:
            estado['sin_confirmar'] += 1

    eventos = []

    def inyectar_fallos():
        time.sleep(4)
        victima = [p['metadata']['name'] for p in pods_procesador()][0]
        cmd(['kubectl', '-n', NS, 'delete', 'pod', victima, '--wait=false'])
        eventos.append(f'delete pod {victima}')
        time.sleep(7)
        cmd(['kubectl', '-n', NS, 'rollout', 'restart', 'deployment/procesador'])
        eventos.append('rollout restart procesador')

    t0 = time.monotonic()
    th = threading.Thread(target=inyectar_fallos)
    th.start()
    with ThreadPoolExecutor(max_workers=hilos) as ex:
        list(ex.map(enviar, lecturas))
    th.join()
    cmd(['kubectl', '-n', NS, 'rollout', 'status', 'deployment/procesador', '--timeout=180s'], check=False)
    duracion = round(time.monotonic() - t0, 1)

    like = f"sensor_id LIKE '{prefijo}-%'"
    q = (f"SELECT (SELECT count(*) FROM lecturas WHERE {like}),"
         f"(SELECT count(*) FROM (SELECT 1 FROM lecturas WHERE {like} GROUP BY sensor_id, ts HAVING count(*)>1) d),"
         f"(SELECT count(*) FROM alertas WHERE severidad='CRITICA' AND {like}),"
         f"(SELECT count(*) FROM lecturas l LEFT JOIN alertas a ON a.sensor_id=l.sensor_id AND a.ts=l.ts "
         f" WHERE l.{like} AND l.severidad IS NOT NULL AND a.id IS NULL)")
    en_bd, duplicados, criticas_bd, sin_alerta = (int(x) for x in sql(q).split('|'))
    res = {
        'prefijo_sensores': prefijo, 'lecturas_enviadas': total, 'lecturas_confirmadas': len(confirmadas),
        'lecturas_en_bd': en_bd, 'lecturas_perdidas': max(len(confirmadas) - en_bd, 0),
        'lecturas_duplicadas': duplicados,
        'alertas_criticas_confirmadas': len(criticas_conf), 'alertas_criticas_en_bd': criticas_bd,
        'alertas_criticas_perdidas': max(len(criticas_conf) - criticas_bd, 0),
        'lecturas_con_alerta_faltante': sin_alerta,
        'reintentos_por_error_transitorio': estado['reintentos'], 'sin_confirmar_tras_20_intentos': estado['sin_confirmar'],
        'fallos_inyectados': eventos, 'duracion_s': duracion,
    }
    res['integridad_verificada'] = (res['lecturas_perdidas'] == 0 and duplicados == 0 and
                                    res['alertas_criticas_perdidas'] == 0 and sin_alerta == 0 and
                                    estado['sin_confirmar'] == 0)
    # E5b: persistencia tras reiniciar PostgreSQL (el PVC conserva los datos)
    antes = int(sql('SELECT count(*) FROM lecturas'))
    cmd(['kubectl', '-n', NS, 'delete', 'pod', '-l', 'app=postgres', '--wait=false'])
    time.sleep(3)
    cmd(['kubectl', '-n', NS, 'rollout', 'status', 'deployment/postgres', '--timeout=240s'])
    for _ in range(30):
        try:
            despues = int(sql('SELECT count(*) FROM lecturas'))
            break
        except RuntimeError:
            time.sleep(2)
    else:
        despues = -1
    res['e5b_total_lecturas_antes_reinicio_postgres'] = antes
    res['e5b_total_lecturas_despues_reinicio_postgres'] = despues
    res['e5b_persistencia_verificada'] = (antes == despues)
    esperar_listos(1)
    (SUMMARY / 'E5_integridad.json').write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding='utf-8')
    print('    E5:', json.dumps({k: res[k] for k in (
        'lecturas_confirmadas', 'lecturas_en_bd', 'lecturas_perdidas', 'lecturas_duplicadas',
        'alertas_criticas_perdidas', 'integridad_verificada', 'e5b_persistencia_verificada')}))
    return res


# ---------------------------------------------------------------- principal

def main():
    global BASE
    ap = argparse.ArgumentParser(description='Experimentos reproducibles E1-E5')
    ap.add_argument('--repeticiones', type=int, default=5)
    ap.add_argument('--duracion', default='30s', help='Ejemplo: 30s o 1m')
    ap.add_argument('--rapido', action='store_true', help='1 repeticion, 10 s: solo verifica el procedimiento')
    ap.add_argument('--solo', nargs='+', choices=['E1', 'E2', 'E3', 'E4', 'E5'],
                    help='Ejecutar solo algunos escenarios (no sobrescribe: guarda en resultados_parcial_*.csv)')
    ap.add_argument('--sin-reset-bd', action='store_true', help='No vaciar las tablas al empezar')
    args = ap.parse_args()
    for programa in ('k6', 'kubectl', 'minikube'):
        if not shutil.which(programa):
            sys.exit(f'Falta instalar {programa}.')
    BASE = base_url()
    if http_json('GET', '/health/live')[0] != 200:
        sys.exit(f'API inaccesible en {BASE}. Ejecuta scripts/deploy.sh o exporta BASE_URL=http://$(minikube ip):30080')
    print(f'API: {BASE}')
    RAW.mkdir(parents=True, exist_ok=True)
    SUMMARY.mkdir(parents=True, exist_ok=True)
    RESOURCE_CSV.write_text('escenario,replicas,vu,instante_utc,pod,cpu_millicores,memoria_mib,observaciones\n', encoding='utf-8')
    if not args.sin_reset_bd:
        sql('TRUNCATE alertas, lecturas RESTART IDENTITY')
    reps = 1 if args.rapido else args.repeticiones
    dur = '10s' if args.rapido else args.duracion
    dur_e4 = '25s' if args.rapido else '40s'
    quiere = lambda e: (not args.solo) or e in args.solo
    rows = []

    if quiere('E1'):
        set_replicas(1)
        calentar()
        for k in range(1, reps + 1):
            print(f'E1 linea base ({k}/{reps})')
            rows.append(run_k6('E1_base', 1, 10, dur, k))
    if quiere('E2'):
        for n in (1, 2, 3):
            set_replicas(n)
            calentar(20)
            for k in range(1, reps + 1):
                print(f'E2 escalabilidad: {n} replicas ({k}/{reps})')
                rows.append(run_k6('E2_escalabilidad', n, 20, dur, k))
    if quiere('E3'):
        set_replicas(2)
        calentar(20)
        for vus in (5, 20, 50):
            for k in range(1, reps + 1):
                print(f'E3 concurrencia {vus} VUs ({k}/{reps})')
                rows.append(run_k6('E3_concurrencia', 2, vus, dur, k))
        fila, ok = e3_idempotencia('10s' if args.rapido else '15s')
        rows.append(fila)
        if not ok:
            print('    !! Regla de idempotencia violada: revisar antes de continuar')
    if quiere('E4'):
        set_replicas(2)
        calentar(20)
        for k in range(1, reps + 1):
            print(f'E4 eliminar un pod durante la carga ({k}/{reps})')
            rows.append(run_k6('E4_fallo_pod', 2, 20, dur_e4, k, inyectar_fallo=True))
            esperar_listos(2)
            time.sleep(5)
    if quiere('E5'):
        set_replicas(2)
        print('E5 integridad: lecturas con reintentos mientras se eliminan y reinician pods')
        e5_integridad(total=600 if args.rapido else 2400)
        set_replicas(2)

    if rows:
        nombre = 'resultados_experimentos.csv' if not args.solo else f'resultados_parcial_{"_".join(args.solo)}.csv'
        destino = ROOT / 'results' / nombre
        with destino.open('w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        print(f'\nResumen: {destino}')
    print('Siguiente: python scripts/graficas.py   y   bash scripts/capturar_entorno.sh')


if __name__ == '__main__':
    main()

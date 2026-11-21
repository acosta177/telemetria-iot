// Todos los VUs envian la MISMA lectura (mismo sensor_id y ts) al mismo tiempo.
// Debe quedar exactamente 1 fila y 1 alerta en PostgreSQL (se verifica en ejecutar_experimentos.py).
import http from 'k6/http';
import { check } from 'k6';
import { Rate } from 'k6/metrics';

const base = (__ENV.BASE_URL || 'http://127.0.0.1:30080').replace(/\/$/, '');
const sensorId = __ENV.SENSOR_ID || 'IDEMP-0001';
const ts = __ENV.TS || '2026-11-19T12:00:00.000000Z';
const errores = new Rate('errores_negocio');

export const options = { vus: Number(__ENV.VUS || 20), duration: __ENV.DURATION || '15s' };

export default function () {
  // Lectura CRITICA a proposito: tambien comprueba que la alerta no se duplique.
  const r = http.post(`${base}/api/v1/lecturas`, JSON.stringify({
    sensor_id: sensorId, ts: ts, temperatura: 95.5, consumo_w: 350.0,
  }), { headers: { 'Content-Type': 'application/json' } });
  const valido = check(r, { 'HTTP 200 o 201 sin duplicado': (x) => x.status === 200 || x.status === 201 });
  errores.add(!valido);
}

export function handleSummary(data) {
  return { [__ENV.SUMMARY_FILE || 'stdout']: JSON.stringify(data, null, 2) };
}

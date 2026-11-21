// Simula cientos de sensores IoT enviando lecturas a la API.
// Variables: BASE_URL, VUS, DURATION, SENSORES (cuantos dispositivos), SENSOR_PREFIX,
//            P_CRITICA (prob. de lectura critica), P_ANOMALIA (prob. de pico anomalo),
//            ESCENARIO, SUMMARY_FILE.
import http from 'k6/http';
import { check } from 'k6';
import { Rate, Counter } from 'k6/metrics';

const base = (__ENV.BASE_URL || 'http://127.0.0.1:30080').replace(/\/$/, '');
const SENSORES = Number(__ENV.SENSORES || 200);
const PREFIJO = __ENV.SENSOR_PREFIX || 'SENS';
const P_CRITICA = Number(__ENV.P_CRITICA || 0.02);
const P_ANOMALIA = Number(__ENV.P_ANOMALIA || 0.02);

const erroresNegocio = new Rate('errores_negocio');
const criticasConfirmadas = new Counter('alertas_criticas_confirmadas');
const lecturasCreadas = new Counter('lecturas_creadas');

export const options = {
  vus: Number(__ENV.VUS || 10),
  duration: __ENV.DURATION || '30s',
  discardResponseBodies: false,
};

function normal(media, desv) {  // Box-Muller
  const u = 1 - Math.random(), v = Math.random();
  return media + desv * Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
}

export default function () {
  // Cada VU recorre sensores distintos; el timestamp lleva el numero de VU en los
  // microsegundos, asi (sensor_id, ts) es unico entre VUs y un 201 siempre es lectura nueva.
  const idx = ((__VU - 1) * 37 + __ITER) % SENSORES;
  const sensorId = `${PREFIJO}-${String(idx).padStart(4, '0')}`;
  const ts = new Date().toISOString().replace('Z', `${String(__VU).padStart(3, '0')}Z`);

  const r = Math.random();
  let temperatura = normal(25 + (idx % 10) * 0.3, 1.5);   // cada sensor tiene su nivel base
  let consumo = normal(300, 40);
  if (r < P_CRITICA) {
    if (Math.random() < 0.5) temperatura = 88 + Math.random() * 20; else consumo = 4100 + Math.random() * 3000;
  } else if (r < P_CRITICA + P_ANOMALIA) {
    temperatura = 45 + Math.random() * 25;  // pico anomalo sin llegar a critico
  }

  const res = http.post(`${base}/api/v1/lecturas`, JSON.stringify({
    sensor_id: sensorId, ts: ts,
    temperatura: Math.round(temperatura * 100) / 100,
    consumo_w: Math.round(consumo * 100) / 100,
  }), { headers: { 'Content-Type': 'application/json' },
        tags: { escenario: __ENV.ESCENARIO || 'carga' } });

  const exito = check(res, { 'HTTP 201 (lectura guardada)': (x) => x.status === 201 });
  erroresNegocio.add(!exito);
  if (exito) {
    lecturasCreadas.add(1);
    try {
      const alerta = res.json('alerta');
      if (alerta && alerta.severidad === 'CRITICA') criticasConfirmadas.add(1);
    } catch (e) { /* cuerpo no JSON: se cuenta solo el error HTTP */ }
  }
}

export function handleSummary(data) {
  return { [__ENV.SUMMARY_FILE || 'stdout']: JSON.stringify(data, null, 2) };
}

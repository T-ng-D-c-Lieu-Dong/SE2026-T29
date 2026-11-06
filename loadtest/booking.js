import http from 'k6/http';
import { check } from 'k6';
import { Counter } from 'k6/metrics';
import {
  options as defaultOptions,
  queryAvailableSlots,
  slotsDuration,
  slotsSuccessRate,
  getTargetDate,
  httpServerErrors,
} from './slots.js';

function positiveInteger(name, fallback) {
  const value = Number(__ENV[name] || fallback);
  if (!Number.isSafeInteger(value) || value < 1) {
    throw new Error(`${name} must be a positive integer`);
  }
  return value;
}

const TARGET_RPS = positiveInteger('TARGET_RPS', 10);
const DURATION = __ENV.DURATION || '10m';
const PRE_ALLOCATED_VUS = positiveInteger('PRE_ALLOCATED_VUS', 10);
const MAX_VUS = positiveInteger('MAX_VUS', 50);
if (MAX_VUS < PRE_ALLOCATED_VUS) throw new Error('MAX_VUS must be >= PRE_ALLOCATED_VUS');

const arrivalProfile = {
  executor: 'constant-arrival-rate',
  timeUnit: '5s',
  duration: DURATION,
  preAllocatedVUs: PRE_ALLOCATED_VUS,
  maxVUs: MAX_VUS,
  gracefulStop: '45s',
};

// At 10 RPS: 4 reads/s + 2 booking flows/s * 3 HTTP requests = 10 HTTP requests/s.
// A failed/empty query or conflict skips writes; inspect actual http_reqs for E15.
function makeScenarios() {
  const scenarios = {
    slots: { ...arrivalProfile, exec: 'listSlots', rate: TARGET_RPS * 2 },
    booking: { ...arrivalProfile, exec: 'createAndCancelBooking', rate: TARGET_RPS },
  };
  if (__ENV.CONFLICT_SCENARIO === 'true') {
    scenarios.conflict = {
      ...arrivalProfile,
      exec: 'createConflictingBooking',
      rate: Math.max(1, Math.floor(TARGET_RPS / 2)),
    };
  }
  return scenarios;
}

export const options = {
  scenarios: makeScenarios(),
  thresholds: {
    ...defaultOptions.thresholds,
    'http_req_duration{name:GET /api/slots}': ['p(95)<500'],
    'http_req_duration{name:POST /api/appointments}': ['p(95)<500'],
    'http_req_duration{name:DELETE /api/appointments/:id}': ['p(95)<500'],
    http_server_errors: ['rate<0.01'],
    checks: ['rate>0.99'],
    bookings_completed: ['count>0'],
    dropped_iterations: ['count==0'],
  },
};

export { slotsDuration, slotsSuccessRate };

export const bookingConflicts = new Counter('booking_conflicts');
export const bookingsCompleted = new Counter('bookings_completed');

const BASE_URL = (__ENV.BASE_URL || 'http://localhost:8000').replace(/\/+$/, '');
const REQUEST_TIMEOUT = '10s';
const TARGET_DATE = getTargetDate();
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function listSlots() {
  return queryAvailableSlots(BASE_URL);
}

export function createAndCancelBooking() {
  bookingsCompleted.add(0);
  bookingConflicts.add(0);
  const { response, success } = queryAvailableSlots(BASE_URL, TARGET_DATE);
  if (!success) return;

  const slots = response.json();
  if (!check(slots, { 'booking has an available slot': (items) => items.length > 0 })) return;
  const slot = slots[Math.floor(Math.random() * slots.length)];
  const created = http.post(
    `${BASE_URL}/api/appointments`,
    JSON.stringify({ customer_name: `k6-${__VU}-${__ITER}`, starts_at: slot.starts_at }),
    {
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      tags: { name: 'POST /api/appointments' },
      timeout: REQUEST_TIMEOUT,
      redirects: 0,
      responseCallback: http.expectedStatuses(201, 409),
    }
  );
  httpServerErrors.add(created.status >= 500 && created.status < 600);
  check(created, { 'booking returns 201 or conflict 409': (res) => [201, 409].includes(res.status) });
  if (created.status === 409) {
    bookingConflicts.add(1);
    return;
  }
  if (created.status !== 201) return;

  let appointment;
  try {
    appointment = created.json();
  } catch (_err) {
    check(null, { 'created booking has a valid id': () => false });
    return;
  }
  if (!check(appointment, { 'created booking has a valid id': (item) => UUID.test(item?.id) })) return;

  // Only cancel the booking created by this iteration, never an existing booking.
  const cancelled = http.del(`${BASE_URL}/api/appointments/${appointment.id}`, null, {
    tags: { name: 'DELETE /api/appointments/:id' },
    timeout: REQUEST_TIMEOUT,
    redirects: 0,
    responseCallback: http.expectedStatuses(204),
  });
  httpServerErrors.add(cancelled.status >= 500 && cancelled.status < 600);
  if (check(cancelled, { 'booking cancellation returns 204': (res) => res.status === 204 })) {
    bookingsCompleted.add(1);
  }
}

export function createConflictingBooking() {
  bookingsCompleted.add(0);
  bookingConflicts.add(0);
  const { response, success } = queryAvailableSlots(BASE_URL, TARGET_DATE);
  if (!success) return;

  const slots = response.json();
  if (!check(slots, { 'conflict booking has an available slot': (items) => items.length > 0 })) return;

  // Deliberately target the very first available slot to maximize concurrency collision / 409
  const slot = slots[0];
  const created = http.post(
    `${BASE_URL}/api/appointments`,
    JSON.stringify({ customer_name: `conflict-k6-${__VU}-${__ITER}`, starts_at: slot.starts_at }),
    {
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      tags: { name: 'POST /api/appointments' },
      timeout: REQUEST_TIMEOUT,
      redirects: 0,
      responseCallback: http.expectedStatuses(201, 409),
    }
  );
  httpServerErrors.add(created.status >= 500 && created.status < 600);
  check(created, { 'conflict booking returns 201 or 409': (res) => [201, 409].includes(res.status) });
  if (created.status === 409) {
    bookingConflicts.add(1);
    return;
  }
  if (created.status !== 201) return;

  let appointment;
  try {
    appointment = created.json();
  } catch (_err) {
    return;
  }
  if (!check(appointment, { 'created conflict booking has valid id': (item) => UUID.test(item?.id) })) return;

  const cancelled = http.del(`${BASE_URL}/api/appointments/${appointment.id}`, null, {
    tags: { name: 'DELETE /api/appointments/:id' },
    timeout: REQUEST_TIMEOUT,
    redirects: 0,
    responseCallback: http.expectedStatuses(204),
  });
  httpServerErrors.add(cancelled.status >= 500 && cancelled.status < 600);
  if (check(cancelled, { 'conflict cancellation returns 204': (res) => res.status === 204 })) {
    bookingsCompleted.add(1);
  }
}

export default createAndCancelBooking;

export function handleSummary(data) {
  const path = __ENV.SUMMARY_PATH || 'reports/loadtest-booking-summary.json';
  const report = {
    ...data,
    metadata: {
      generated_at: new Date().toISOString(),
      base_url: BASE_URL,
      target_date: TARGET_DATE,
      target_rps: TARGET_RPS,
      configured_duration: DURATION,
      scenarios: makeScenarios(),
      release: __ENV.BOOKING_RELEASE || 'unspecified',
      commit_sha: __ENV.BOOKING_COMMIT_SHA || 'unspecified',
      environment: __ENV.TEST_ENVIRONMENT || 'unspecified',
      dataset: __ENV.DATASET || 'unspecified',
    },
  };
  const metrics = data.metrics || {};
  const count = metrics.http_reqs?.values.count ?? 0;
  const rate = metrics.http_reqs?.values.rate ?? 0;
  const p95 = metrics.http_req_duration?.values['p(95)'] ?? 'n/a';
  const failedThresholds = Object.entries(metrics).flatMap(([name, metric]) =>
    Object.entries(metric.thresholds || {})
      .filter(([, result]) => !result.ok)
      .map(([threshold]) => `${name}: ${threshold}`)
  );
  return {
    [path]: JSON.stringify(report, null, 2) + '\n',
    stdout: `HTTP requests: ${count}, rate: ${rate}/s, p95: ${p95} ms\n` +
      `Failed thresholds: ${failedThresholds.join('; ') || 'none'}\nSummary: ${path}\n`,
  };
}

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Trend, Rate } from 'k6/metrics';

// Custom metrics for granular observability
export const slotsDuration = new Trend('slots_duration', true);
export const slotsSuccessRate = new Rate('slots_success_rate');
export const httpServerErrors = new Rate('http_server_errors');

// Default test configuration and thresholds aligned with E15
export const options = {
  vus: parseInt(__ENV.VUS || '5', 10),
  duration: __ENV.DURATION || '30s',
  thresholds: {
    // E15 requirement: 95% latency under 500ms
    http_req_duration: ['p(95)<500'],
    slots_duration: ['p(95)<500'],
    // Error rate must remain below 1%
    http_req_failed: ['rate<0.01'],
    slots_success_rate: ['rate>0.99'],
  },
};

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';

/**
 * Helper to compute the target query date.
 * Defaults to tomorrow (YYYY-MM-DD) to ensure querying upcoming available slots.
 */
export function getTargetDate() {
  if (__ENV.TARGET_DATE) {
    return __ENV.TARGET_DATE;
  }
  const target = new Date();
  target.setDate(target.getDate() + 1);
  const year = target.getFullYear();
  const month = String(target.getMonth() + 1).padStart(2, '0');
  const day = String(target.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

/**
 * Execute a single query to the slots endpoint and validate the response contract.
 */
export function queryAvailableSlots(baseUrl = BASE_URL, dateStr = getTargetDate()) {
  const url = `${baseUrl}/api/slots?date=${dateStr}`;
  const params = {
    headers: {
      'Accept': 'application/json',
      'User-Agent': 'k6-loadtest/1.0',
    },
    tags: { name: 'GET /api/slots' },
    timeout: '10s',
    redirects: 0,
    responseCallback: http.expectedStatuses(200),
  };

  const startTime = Date.now();
  const res = http.get(url, params);
  httpServerErrors.add(res.status >= 500 && res.status < 600);
  const duration = Date.now() - startTime;

  slotsDuration.add(duration);

  let isJsonArray = false;
  let allSlotsHaveTimestamps = false;

  if (res.status === 200) {
    try {
      const data = JSON.parse(res.body);
      if (Array.isArray(data)) {
        isJsonArray = true;
        allSlotsHaveTimestamps = data.every(
          (slot) => typeof slot === 'object' && slot !== null && typeof slot.starts_at === 'string'
        );
      }
    } catch (_err) {
      isJsonArray = false;
    }
  }

  const success = check(res, {
    'status is 200': (r) => r.status === 200,
    'response body is json array': () => isJsonArray,
    'slots have valid starts_at': () => allSlotsHaveTimestamps,
  });

  slotsSuccessRate.add(success);
  return { response: res, success };
}

/**
 * Default scenario execution loop
 */
export default function () {
  queryAvailableSlots();
  sleep(1);
}

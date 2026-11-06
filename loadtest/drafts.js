// VT-115 — load check for draft autosave: 100 concurrent users, target p95 <= 3000 ms.
//
// Scenario "own_drafts": 100 VUs, each autosaving its own draft with increasing revisions.
// Scenario "hot_draft":  100 VUs all autosaving the SAME draft (worst-case row contention:
//                        every write queues on one row lock).
// Both run back-to-back with no think time, which is harsher than a real debounced
// autosave (one save per ~1-2 s per user).
//
// Run:  k6 run -e BASE_URL=http://localhost:8000 --summary-export=summary.json loadtest/drafts.js
// Then: python loadtest/check_drafts.py summary.json   (verifies hot draft == max revision)
import http from 'k6/http';
import { check } from 'k6';
import exec from 'k6/execution';
import { Rate, Trend } from 'k6/metrics';

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
const VUS = Number(__ENV.VUS || 100);
const DURATION = __ENV.DURATION || '60s';
// Fixed id so the post-check can read it back. Change per run if the DB is reused.
const HOT_DRAFT_ID = __ENV.HOT_DRAFT_ID || '00000000-0000-4000-8000-000000000115';

export const serverErrors = new Rate('draft_server_errors');
export const unexpectedStatus = new Rate('draft_unexpected_status');
export const hotRevisionSent = new Trend('hot_revision_sent');

export const options = {
  scenarios: {
    own_drafts: { executor: 'constant-vus', vus: VUS, duration: DURATION, exec: 'ownDraft' },
    hot_draft: {
      executor: 'constant-vus',
      vus: VUS,
      duration: DURATION,
      exec: 'hotDraft',
      startTime: DURATION,
    },
  },
  thresholds: {
    'http_req_duration{scenario:own_drafts}': ['p(95)<3000'],
    'http_req_duration{scenario:hot_draft}': ['p(95)<3000'],
    draft_server_errors: ['rate<0.01'],
    draft_unexpected_status: ['rate==0'],
  },
};

// Revisions start from a per-run base so a re-run against the same database still sends
// NEWER revisions. (Run 2 restarted at 1 and the server correctly rejected every save as
// stale - a test-data bug, see docs/vt115/evidence/09-load-k6-run2.log.)
export function setup() {
  return { base: Date.now() * 1000 }; // ~1.8e15 < Number.MAX_SAFE_INTEGER (9.0e15)
}

function uuidFor(vu) {
  // Deterministic per-VU draft id: test data is reproducible across runs.
  const hex = vu.toString(16).padStart(12, '0');
  return `11500000-0000-4000-8000-${hex}`;
}

function save(draftId, revision, scenario) {
  const response = http.put(
    `${BASE_URL}/api/drafts/${draftId}`,
    JSON.stringify({
      revision,
      customer_name: `Khách ${exec.vu.idInTest} rev ${revision}`,
      starts_at: '2026-12-01T09:30:00+07:00',
    }),
    { headers: { 'Content-Type': 'application/json' }, tags: { name: 'PUT /api/drafts/{id}' } },
  );
  serverErrors.add(response.status >= 500);
  unexpectedStatus.add(response.status !== 200 && response.status !== 409);
  check(response, { [`${scenario}: 200 or 409`]: (r) => r.status === 200 || r.status === 409 });
  return response;
}

export function ownDraft(data) {
  // Only this VU writes this draft, so every save must be accepted (200).
  const revision = data.base + exec.vu.iterationInScenario + 1;
  const response = save(uuidFor(exec.vu.idInTest), revision, 'own_drafts');
  check(response, { 'own_drafts: newer revision accepted': (r) => r.status === 200 });
}

export function hotDraft(data) {
  // Globally unique, increasing revision across all VUs; arrival order is not guaranteed,
  // so some saves are legitimately stale (409).
  const revision = data.base + exec.scenario.iterationInTest + 1;
  hotRevisionSent.add(revision);
  save(HOT_DRAFT_ID, revision, 'hot_draft');
}

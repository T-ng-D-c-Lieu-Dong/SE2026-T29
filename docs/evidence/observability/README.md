# Observability drill evidence — TASK-006

This directory stores the reproducible queries and the evidence captured from the shared demo
environment. Configuration files and local tests show that the observability path is ready to
run; they do not replace screenshots and timestamps from the real Collector, Grafana and alert
delivery path.

## Before the drill

Record these values in `result.md` before generating traffic:

- UTC start and end time;
- Git commit, release and backend image digest;
- demo host CPU, RAM and disk;
- fault mode, rate and expiry time;
- load rate and duration; and
- Grafana, Prometheus, Tempo, Loki and Collector versions.

Use one fixed Grafana time range for the dashboard, trace and log screenshots. Keep customer
names and request bodies out of every artifact.

## E09 — Request error across metrics, trace and log

1. Generate requests while the bounded `error` fault is active.
2. In Prometheus or Grafana, confirm traffic and the 5xx ratio:

   ```promql
   sum by (http_target) (
     rate(http_server_duration_milliseconds_count{service_name="booking-api"}[1m])
   )
   ```

   ```promql
   booking:http_5xx_ratio:rate1m
   ```

3. In Tempo, find an error trace for the affected release:

   ```traceql
   { resource.service.name = "booking-api" && span.http.response.status_code >= 500 }
   ```

4. Copy its 32-character trace ID and query Loki:

   ```logql
   {service_name="booking-api"} | trace_id = "<trace-id>"
   ```

5. Confirm that the trace and log have the same trace ID, route template, status and
   `service_version`. Confirm that no metric label contains an appointment UUID, trace ID or
   customer data.
6. Save `e09-dashboard.png`, `e09-trace.png` and `e09-log.png` in this directory.

The provisioned links should also support dashboard exemplar → Tempo trace, Tempo span → Loki
logs and Loki trace ID → Tempo trace. Record whether each direction worked in `result.md`.

## E10 — Collector outage does not block booking

The unit test `test_collector_outage_does_not_block_booking_path` covers bounded batch isolation.
Repeat it against the demo stack:

1. Stop only the Collector and record the timestamp.
2. Create and read a booking through the API or UI.
3. Record response status and duration; the booking must succeed without waiting indefinitely.
4. Start the Collector and confirm the API remained ready.

Do not infer telemetry delivery during the outage from this test; its pass condition is business
availability while export is unavailable.

## E11 — High error-rate alert

With at least 100 requests per minute, make more than 5% return 5xx for long enough to satisfy
the two-minute `for` duration. Record:

- fault start;
- Prometheus alert pending and firing timestamps;
- receiver notification timestamp;
- mitigation timestamp; and
- resolved timestamp.

Save `e11-alert-firing.png`, `e11-notification.png` and `e11-alert-resolved.png`. Alert delivery
must occur within the project's three-minute target measured from the first full qualifying
window.

## E16 — Independent readiness probe

1. Stop the Booking API while Prometheus, blackbox exporter and Alertmanager remain running.
2. Confirm `probe_success{job="booking-api-readiness"} == 0`.
3. Confirm `ApiProbeDown` fires after one minute even though API HTTP counters no longer increase.
4. Restart the API, confirm readiness and wait for the resolved notification.
5. Save `e16-probe-down.png` and `e16-alert.png`.

The blackbox exporter runs on the same demo VM. State this limitation in `result.md`: it detects
an API or readiness dependency failure, but it cannot send evidence when the entire VM or its
network is unavailable.

## Result template

Create `result.md` only after the drill, using this table:

| Evidence | Result | Timestamp / duration | Artifact or link | Notes |
| --- | --- | --- | --- | --- |
| E09 metric → trace → log | Pending | — | — | — |
| E10 booking during Collector outage | Pending | — | — | — |
| E11 firing and resolved alert | Pending | — | — | — |
| E16 independent probe alert | Pending | — | — | — |

Replace `Pending` only with an observed result. Include failed attempts because they explain the
limits of the demo and guide follow-up work.

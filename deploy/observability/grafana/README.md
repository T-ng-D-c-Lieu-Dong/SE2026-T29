# Booking API Grafana content

Provision `dashboards/booking-api-overview.json` from the Grafana dashboards provider. The
dashboard expects a Prometheus datasource with UID `prometheus`.

Mount `provisioning/` at `/etc/grafana/provisioning` and `dashboards/` at
`/var/lib/grafana/dashboards`. The datasource provisioning creates stable UIDs for Prometheus,
Tempo and Loki and configures all three correlation directions:

- Prometheus exemplars open the matching Tempo trace;
- a Tempo span opens Loki logs for its service and native trace ID; and
- Loki's `trace_id` structured metadata opens the matching Tempo trace.

The Collector Prometheus exporter must retain the default metric suffixes and expose these
resource attributes as normalized labels:

- `service.name` → `service_name`
- `service.version` → `service_version`
- `commit_sha` → `commit_sha`

Use `resource_constant_labels.included` for those attributes (or
`resource_to_telemetry_conversion.enabled: true` on older Collector versions). Enable OpenMetrics
on the exporter so histogram exemplars can link dashboard samples to Tempo traces.

The dashboard consumes:

- FastAPI histogram `http_server_duration_milliseconds` and route-template label `http_target`;
- business counter `booking_conflicts_total`;
- deployment gauge `booking_deployment_timestamp_seconds`;
- blackbox metric `probe_success{job="booking-api-readiness"}`;
- node-exporter host metrics; and
- cAdvisor container metrics and `container_label_com_docker_compose_service`.

If the infrastructure owner changes the exporter translation strategy, update the metric names
in this dashboard and the Prometheus rules together. Never replace `http_target` with a raw path,
appointment UUID or trace ID.

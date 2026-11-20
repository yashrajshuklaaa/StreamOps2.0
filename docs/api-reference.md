# API Reference

This reference describes the current Go control plane in
`services/control-plane/`. It currently supports Ollama's
`/api/generate` route; the legacy Python service has additional routes that
are not part of this Go/Rust prototype.

## `POST /api/generate`

Forwards an Ollama generation request and streams the upstream NDJSON response.
Each response chunk is also sent to the Rust intent service. When the intent
service returns a trigger decision, the Go control plane creates a Kubernetes
pod asynchronously.

The response includes an `X-StreamOps-Session-ID` header. Keep this value if
you want to claim the corresponding speculative pod. A triggered pod is an
idle sandbox; this endpoint does not execute generated code or tool calls.

## `POST /v1/sessions/{session_id}/claim`

Marks an existing speculative pod as claimed and waits for it to become ready.
It does not run a tool payload.

Example:

```http
POST /v1/sessions/0123456789abcdef0123456789abcdef/claim
Content-Type: application/json

{"tool_name":"python"}
```

The response contains the pod name, namespace, readiness status, and timing
fields. Timing returned by this endpoint is not an end-to-end TTFE measurement.

## `GET /healthz` and `GET /readyz`

`/healthz` indicates that the Go process is running. `/readyz` checks the
configured Kubernetes namespace API and Rust intent service.

## `GET /metrics`

Exposes Go process metrics and the following Stream-Ops counters/histograms:

- `streamops_intent_triggers_total`
- `streamops_pod_create_errors_total`
- `streamops_pod_trigger_to_ready_seconds`
- `streamops_cold_start_seconds_masked_total`
- `streamops_speculative_pods_reclaimed_total`

The metric named `streamops_cold_start_seconds_masked_total` currently
calculates the overlap of a recorded pod-ready time and a claim request. It
does not establish an agent-generated tool call or an end-to-end latency
benefit; interpret it as a prototype diagnostic only.

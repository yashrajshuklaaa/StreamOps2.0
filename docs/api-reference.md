# API & Protocol Reference

Stream-Ops exposes standard OpenAI and Ollama compatible endpoints alongside telemetry and observability hooks.

---

## Endpoints

### 1. `POST /api/generate`
Proxies streaming generation requests with real-time speculative lookahead.

**Request Body (NDJSON/JSON):**
```json
{
  "model": "llama3:8b",
  "prompt": "Analyze this data in Python and compute averages.",
  "stream": true
}
```

**Response:**
Streams NDJSON chunks while concurrently triggering Kubernetes pod pre-warming in the background.

---

### 2. `POST /v1/chat/completions`
OpenAI-compatible chat completion proxy supporting Server-Sent Events (SSE).

**Request Body:**
```json
{
  "model": "gpt-4o",
  "messages": [
    {"role": "user", "content": "Query the PostgreSQL database for user registrations."}
  ],
  "stream": true
}
```

---

### 3. `GET /metrics`
Prometheus metrics endpoint.

**Key Metrics:**
- `streamops_tokens_processed_total`: Total streaming tokens processed.
- `streamops_intents_detected_total`: Speculative intents triggered per tool.
- `streamops_pod_provision_seconds`: Latency distribution of pod provisioning.
- `streamops_latency_masked_seconds_total`: Cumulative cold-start seconds masked.
- `streamops_active_sandboxes`: Gauge of currently active pods.
- `streamops_finops_saved_usd_total`: Total calculated dollar value saved.

---

### 4. `GET /healthz` & `GET /readyz`
Liveness and Readiness health checks.

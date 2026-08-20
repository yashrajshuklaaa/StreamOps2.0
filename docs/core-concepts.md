# Core Concepts

Stream-Ops relies on three foundational components to achieve just-in-time infrastructure provisioning: **Streaming Adapters**, the **Intent Detector**, and the **Kubernetes Provisioner**.

## Provider-Agnostic Streaming

The core requirement of Stream-Ops is the ability to receive LLM output incrementally (streaming) and inspect those events before the response is complete.

Different LLMs emit streams in different formats:
- **OpenAI / Anthropic**: Server-Sent Events (SSE) Delta Stream.
- **Ollama**: NDJSON (Newline Delimited JSON).

Stream-Ops solves this using an abstraction layer called `StreamingAdapter`. The proxy routes the request to the correct adapter, which normalizes the chunked bytes into a pure text stream. This ensures the infrastructure logic remains completely decoupled from the AI provider.

## Confidence-Based Intent Detection

Instead of relying on rigid, hardcoded regular expressions (e.g., `if "python" in text`), Stream-Ops utilizes a weighted **Confidence Scoring** system within the `IntentDetector`.

As tokens stream in, the detector calculates a running confidence score based on keywords. 
For example:
- `python` (+0.5)
- `pandas` (+0.5)

If the cumulative score crosses the threshold (e.g., `0.8`), the detector confidently emits a `ResourceDecision`. This allows the system to differentiate between a casual mention of a tool and an actual intent to execute code.

## Lifecycle Management & Garbage Collection

A common critique of pre-warming infrastructure is the potential waste of memory and compute resources if the LLM changes its mind and doesn't end up using the pre-warmed pod.

Stream-Ops solves this via a background **Garbage Collection TTL Loop**:
1. When a pod is provisioned, it is tagged with `streamops-ttl: active`.
2. A background thread continually monitors the age of all active pods.
3. If a pod sits unused for 60 seconds (its Time-To-Live), Kubernetes automatically deletes it, ensuring zero resource leakage.

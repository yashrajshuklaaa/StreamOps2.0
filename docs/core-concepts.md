# Core Concepts

The current prototype contains a Rust intent-scoring service and a Go Ollama-to-Kubernetes control plane. It is not yet a general multi-provider agent integration.

## Ollama stream inspection

The Go proxy handles Ollama's newline-delimited `/api/generate` response and sends each `response` value to the Rust service. It does not currently normalize OpenAI, Anthropic, or DeepSeek streams, and it does not establish access to private chain-of-thought.

## Heuristic intent score

The Rust service combines keyword matching and TF-IDF-style lexical similarity. It passes a heuristic score to a cost threshold derived from static tool-profile constants. The score is **not calibrated as a probability**, and a tool mention does not establish that the agent will execute that tool.

## Pod lifecycle

The Go service creates a namespaced pod after a trigger, offers an endpoint to mark it claimed, observes readiness, and periodically deletes unclaimed pods after the configured TTL. Claiming is not tool execution. TTL cleanup does not guarantee zero resource leakage, and security/isolation properties have not been independently evaluated.

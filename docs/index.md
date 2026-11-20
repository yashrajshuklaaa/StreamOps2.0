# Welcome to Stream-Ops 2.0

**Stream-Ops** is a research prototype for exploring speculative sandbox prewarming in tool-using LLM systems. Performance benefits have not yet been evaluated.

```
[ Streamed Ollama response text ] ──► [ Rust heuristic intent scorer ]
                                           └──► [ Go requests a Kubernetes pod ]
```

---

## The Core Problem: The Cold Start Dilemma

Creating a Kubernetes pod can add infrastructure delay. Its size depends on the cluster, image cache, scheduling conditions, and runtime; this repository has not established a general cold-start range.

| Strategy | Latency Impact | Cloud Compute Cost | Security & Isolation |
| :--- | :--- | :--- | :--- |
| **Always-On Static Pods** | ⚡ Instant (0s) | 💸 **Extremely Wasteful** (Hundreds of idle pods) | ⚠️ Risk of cross-tenant state leakage |
| **On-Demand Reactive Pods** | 🐢 **5–15s Cold Penalty** | 💰 Minimal cost | ✅ Fresh container per session |
| **Stream-Ops prototype** | Not evaluated | Not evaluated | Creates isolated-by-session named pods; isolation requires further review |

---

## Key Highlights

- Rust scores ordinary Ollama response chunks using keywords and lexical similarity.
- Go can create a real Kubernetes pod and delete expired unclaimed speculative pods.
- The threshold uses static profile values; the score is not a calibrated probability.
- The claim endpoint marks a pod claimed and waits for readiness; it does not execute tool code.
- Performance, cost savings, multi-provider compatibility, and production isolation are not evaluated.

---

## Quick Navigation

- [Scientific Research Paper](RESEARCH_PAPER.md)
- [System Architecture](architecture.md)
- [Bayesian FinOps Engine](finops.md)
- [Cloud Deployment Guide](deployment.md)
- [API Reference](api-reference.md)
- [Getting Started Runbook](getting-started.md)

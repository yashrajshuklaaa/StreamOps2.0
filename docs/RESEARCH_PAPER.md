# Stream-Ops: A Prototype for Speculative Sandbox Prewarming in LLM Agent Systems

**Status:** Prototype report; performance evaluation is not yet complete.
**Project:** Stream-Ops, group K3C0047
**Repository:** <https://github.com/yashrajshuklaaa/StreamOps2.0>

## Abstract

Tool-using language-model agents can incur infrastructure delay when an execution
environment is created only after a tool call. Stream-Ops explores whether a
sandbox can be provisioned while an agent response is still streaming. The
current prototype uses a Rust service to score streamed Ollama response text
and a Go service to request a namespaced Kubernetes pod when a score passes a
heuristic cost threshold. The services can be run locally in Kind.

This is an implementation report, not evidence of a latency improvement. The
repository does not yet contain a reproducible agent-to-tool execution
evaluation, a reactive baseline, or raw benchmark traces. The earlier speedup,
cold-start masking, cloud-cost, and proxy-overhead figures are withdrawn.
The prototype provisions an idle sandbox pod; it does not yet execute an
agent's tool call inside that pod.

## 1. Scope and positioning

The hypothesis is that signals available before a formal tool invocation may
provide time to start a sandbox concurrently with model generation. Whether a
provider exposes useful reasoning signals is provider- and API-dependent.
Stream-Ops currently inspects ordinary streamed Ollama `response` text; it does
not establish access to private chain-of-thought or infer that generated text
faithfully represents a later action.

Intent-aware sandbox prewarming is not new: SpecBox describes keyword and
streaming-embedding intent detection, sandbox prewarming, and context-aware
prefetching over a sandbox dependency graph [4]. Conveyor overlaps partial
tool execution with decoding [2], Speculative Actions speculates on agent
actions [3], and Continuum manages model KV-cache retention across agent tool
calls [5]. These are related but distinct system mechanisms. This prototype
does not claim to introduce intent-aware prewarming or to outperform these
systems.

The limited contribution of the current artifact is an open, locally runnable
Rust intent-scoring service connected to a Go Kubernetes pod lifecycle
service, together with a testable Kind deployment. A cost-aware policy and
rigorous comparison remain research goals, not established contributions.

## 2. Prototype implementation

The Rust service keeps bounded text state per stream session, applies
keyword matching and a TF-IDF-style term-frequency/inverse-document-frequency
similarity score, and evaluates the score against a threshold computed from
static tool cost-profile values. These scores are heuristic; they are not
calibrated probabilities. The current threshold uses configured constants,
not live cloud prices or measured distributions.

The Go service proxies Ollama's newline-delimited generation response, sends
each response chunk to the Rust service, and creates a namespaced Kubernetes
pod when the service returns a trigger decision. It exposes a claim endpoint,
pod readiness observation, TTL cleanup for unclaimed speculative pods, and
Prometheus metrics.

The current implementation is a prototype, not a production Kubernetes
operator. It supports the Ollama generation route only. The Python sandbox
starts a sleeping process; the claim endpoint marks the pod as claimed and
waits for readiness but does not execute code or accept an agent tool-call
payload. There is no end-to-end agent integration, shared trace schema,
provider adapter suite, OpenTelemetry instrumentation, preemptible priority
class, or real tool execution yet.

## 3. Decision-policy status

The implementation's static threshold is a heuristic policy, not the
lookahead-aware optimal-stopping policy proposed for future work. In
particular, the detector's score is not a calibrated estimate of
\(P(\text{tool }k\text{ is called}\mid\text{stream so far})\). The current
cost profile uses hard-coded values and a fixed TTL, and does not model
remaining reasoning time, an abort-time distribution, or the hidden portion
of cold start.

Consequently, no optimality theorem or bounded-regret result is claimed here.
Deriving and testing a race model, a lookahead-dependent decision rule, and
hazard-rate or budget-aware cleanup policies are future work. The previous
fixed-boundary derivation must not be interpreted as a proof for the deployed
implementation.

## 4. Evaluation status

**Performance evaluation: NOT EVALUATED.**

There are no raw evaluation traces or result files under `results/`. The
existing `benchmarks/benchmark_suite.py` computes TTFE and masking values from
fixed token rates, cold-start constants, and a chosen trigger offset; its
short sleeps do not measure those modeled durations. Its printed table is
**SIMULATED**, not measured. `benchmark_compare.py` is also a timing
demonstration based on fixed sleeps, not a benchmark of model inference or
Kubernetes startup.

The earlier paper's numerical TTFE table, claimed 1.70x maximum speedup,
100% masking claim, 5–15-second general cold-start claim, cloud-cost savings,
proxy-overhead measurements, and EKS/500-prompt/model evaluation description
are withdrawn. They are unsupported by retained scripts and raw data and must
not be cited as results. The local Kind smoke test demonstrated that a real
Ollama stream can trigger creation of a real Kubernetes pod, but did not
compare reactive and speculative end-to-end tool execution. It is not a
latency experiment.

### Evaluation required before making performance claims

The next evaluation should pre-register workloads, model/provider versions,
cluster configuration, policies, and metrics. It should retain raw per-run
traces and report at least:

- TTFE p50/p95/p99 for reactive and speculative execution;
- measured cold-start and reasoning intervals, including their overlap;
- prewarm precision, recall, hit rate, and wasted pod-seconds;
- resource and cost measurements with the price source and date;
- direct-inference proxy overhead and confidence intervals.

No sample count, improvement, cost saving, or confidence interval is reported
until that evaluation has been run and its outputs are reproducible from
versioned scripts and raw data.

## 5. Limitations and threats to validity

The current detector uses keyword and small-corpus lexical similarity, not a
trained or calibrated intent model. Streamed response text can mention a tool
without calling it, omit a later tool call, or be unrelated to an internal
reasoning process. Research on chain-of-thought faithfulness cautions against
treating visible explanations as reliable records of model reasoning [6].
Provider-specific stream fields and availability must be verified and
evaluated separately; no general claim about access to private reasoning is
made.

Kind smoke tests do not represent a production cluster's scheduler, image
cache, network, contention, security boundary, or cloud pricing. Pod
readiness is not equivalent to a working tool runtime, and claiming a pod is
not tool execution. The prototype currently has no concurrent load study,
reactive baseline, calibration analysis, statistical confidence intervals, or
failure-injection evaluation.

## References

1. Shunyu Yao, Jeffrey Zhao, Dian Yu, Nan Du, Izhak Shafran, Karthik
   Narasimhan, and Yuan Cao. “ReAct: Synergizing Reasoning and Acting in
   Language Models.” arXiv:2210.03629 (2022; ICLR 2023).
   <https://arxiv.org/abs/2210.03629>
2. Yechen Xu, Xinhao Kong, Tingjun Chen, and Danyang Zhuo. “Conveyor:
   Efficient Tool-aware LLM Serving with Tool Partial Execution.”
   arXiv:2406.00059 (2024).
   <https://arxiv.org/abs/2406.00059>
3. Naimeng Ye, Arnav Ahuja, Georgios Liargkovas, Yunan Lu, Kostis Kaffes,
   and Tianyi Peng. “Speculative Actions: A Lossless Framework for Faster
   Agentic Systems.” arXiv:2510.04371 (2025; revised 2026).
   <https://arxiv.org/abs/2510.04371>
4. Yihui Zhang, Tianyu Wo, Jinghao Wang, Xiaoyang Sun, Menghao Zhang,
   Cangzhou Yuan, Li Li, Chunming Hu, Albert Y. Zomaya, and Renyu Yang.
   “SpecBox: Speculative Sandbox Scheduling for Efficient LLM Agent
   Serving.” arXiv:2607.23933 (2026).
   <https://arxiv.org/abs/2607.23933>
5. Hanchen Li, Runyuan He, Qiuyang Mang, Qizheng Zhang, Huanzhi Mao,
   Xiaokun Chen, Hangrui Zhou, Huanchen Zhang, Alvin Cheung, Joseph
   Gonzalez, and Ion Stoica. “Continuum: Efficient and Robust Multi-Turn
   LLM Agent Scheduling with KV Cache Time-to-Live.” arXiv:2511.02230
   (2025; revised 2026).
   <https://arxiv.org/abs/2511.02230>
6. Yanda Chen et al. “Reasoning Models Don't Always Say What They Think.”
   arXiv:2505.05410 (2025).
   <https://arxiv.org/abs/2505.05410>

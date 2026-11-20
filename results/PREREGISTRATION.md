# Stream-Ops local controlled experiment preregistration

**Status:** Frozen before experiment trials. No trials have been run under this protocol.

## Research question and hypothesis

Does prewarming a Python executor pod from the streamed assistant text reduce
time from request start to actual Python execution, compared with creating the
same pod only after the formal `python_exec` tool call?

The null result is no reduction or a regression in speculative TTFE. Results,
failures, false positives, and runs without a tool call will all be reported.
The benchmark suite's former simulated values are not inputs to this experiment.

## Frozen environment and source audit

Versions selected from the existing local cluster, then checked against
upstream documentation on 2026-11-20:

- Ollama API: `POST /api/chat`, streamed NDJSON, with formal `message.tool_calls`.
  The current official API and tool-calling documentation describe this shape:
  <https://docs.ollama.com/api/chat> and
  <https://docs.ollama.com/capabilities/tool-calling>.
- Ollama server image: `ollama/ollama:0.6.5`, the version already running in
  the local cluster. Its release is recorded at
  <https://github.com/ollama/ollama/releases/tag/v0.6.5>.
- Model: `qwen3:1.7b`, Q4_K_M. The official Ollama library describes the
  1.7B Q4_K_M artifact and lists its model identifier prefix
  `8f68893c685c`: <https://ollama.com/library/qwen3:1.7b>. Before trials,
  `env.json` must record the full digest reported by Ollama; abort if it does
  not match the preregistered artifact prefix.
- Kind: `v0.27.0`; its release specifies Kubernetes `v1.32.2` and the matching
  node-image digest:
  <https://github.com/kubernetes-sigs/kind/releases/tag/v0.27.0>.
- Kubernetes Go client: `client-go v0.32.3`, matching the running Kubernetes
  `v1.32.2` minor. Upstream's compatibility matrix marks client-go `v0.32.0`
  as the exact match for Kubernetes 1.32:
  <https://github.com/kubernetes/client-go#compatibility-matrix>.
- Kubernetes CLI: use `kubectl v1.32.2` for experiment setup and reset. The
  currently installed `kubectl v1.37.2` is outside the supported version skew
  for this v1.32.2 cluster and must not be used for trial control.

The locally built executor image and the exact running image IDs, Go/Rust
compiler versions, OS/kernel, resource limits, model digest, cluster version,
git SHA, and configuration will be captured in `results/env.json` before the
first trial. The local cluster shares one host for Ollama and Kubernetes;
host CPU load will be recorded as a confound. All experiment resource-cost
results are resource-seconds only, never dollars.

## Conditions and randomization

- **A — reactive:** do not run the intent scorer; create the executor pod only
  after the fully parsed `python_exec` tool call.
- **B — speculative:** send text deltas to the asynchronous heuristic tap and
  request the executor pod on a qualifying trigger. Atomically claim a matching
  pod at tool-call time; if none exists, create an identical pod reactively.
- An eager condition is not included.
- Primary image state is pre-pulled for both conditions. Cold-pull image state
  is a separate factor and is **not evaluated** in this experiment.
- For each primary task and repetition, randomize A/B order with a fixed,
  recorded seed. Reset and verify that no experiment sandbox pods remain
  between runs. Keep the model resident and discard three model warm-up runs.
- The model, prompt, sampling parameters, executor image digest, pod spec,
  cluster, gateway build, and resource limits are held constant across A/B.
- Task-level pairing is used for analysis. Model output may vary between runs;
  reasoning duration is measured, not assumed equal.

## Workloads

The primary tasks each require exactly one `python_exec` call. Executor output
is compared byte-for-byte, after trimming the final newline, with the expected
answer:

1. `python_mul`: print `137 * 269`; expected output `36853`.
2. `python_sum`: print `sum(range(1, 101))`; expected output `5050`.
3. `python_pow`: print `2 ** 20`; expected output `1048576`.
4. `python_squares`: print `sum(i * i for i in range(1, 51))`; expected
   output `42925`.

The agent receives one `python_exec` function tool and a deterministic
instruction to use it. The system records task success from the actual
executor output, not the model's final prose.

Minimum primary sample: 30 repetitions per task per condition (240 primary
runs total). Three warm-ups per model are excluded from primary analysis and
will be recorded separately. Target at least 500 runs per condition for
stable p99 estimation; if fewer are achieved, p99 is labelled indicative and
shown with its bootstrap interval.

## Event and trace schema

The gateway is the primary clock. Each event records gateway monotonic
nanoseconds since process start and UTC wall time. The executor additionally
reports its wall and monotonic clock readings; the gateway records a
four-timestamp clock-offset estimate and round-trip uncertainty. Kubernetes
object timestamps are cross-checks only, never the primary timing source.

Each run trace contains event records for:
`request_start`, `first_token`, `spec_trigger`, `toolcall_emitted`,
`pod_create_requested`, `pod_created`, `pod_ready`, `claim_start`,
`claim_end`, `exec_start`, `first_tool_result`, `task_end`, `pod_deleted`,
and `cleanup_done`, plus a final `run_summary`. Events carry `run_id`,
`task_id`, `condition`, `run_order_index`, `seed`, path, and failure reason.
Text/CoT contents are not stored; intent events store only the uncalibrated
heuristic score, tool, and policy version.

## Metrics and failure treatment

- Primary: `TTFE = exec_start - request_start`.
- Secondary: `post_call_wait = exec_start - toolcall_emitted`;
  `pod_ready_wait = max(0, pod_ready - toolcall_emitted)`; task duration; and
  exact-output task success rate.
- Paths: `hit`, `late_hit`, `wrong_tool`, `no_spec_fallback`, or `reactive`.
- Speculation quality: hit, late-hit, wrong-tool, false-positive (speculative
  pod never claimed), and false-negative (tool call without a matching
  speculative pod) rates.
- Cost proxy: unclaimed pod-seconds, total pod-seconds, and requested
  CPU/memory resource-seconds.
- Report p50/p95/p99 and bootstrap 95% confidence intervals. With under 500
  observations per condition, p99 is explicitly indicative.
- All assigned runs remain in the run log (intention-to-treat). Failed,
  timed-out, and no-tool-call runs are reported in separate count tables and
  are not silently discarded. Latency quantiles are reported for runs with a
  valid `exec_start`, alongside their denominator and task-success rate.

## Analysis plan

`results/scripts/analyze.py` will deterministically read only
`results/raw/*.jsonl`. It will compute paired per-task differences, Wilcoxon
signed-rank tests, Hodges-Lehmann estimates, paired bootstrap intervals for
median/p95/p99 differences, and Cliff's delta. It will emit a benefit/cost
trade-off table, per-run scatter plot, and ECDFs. Failed and null runs remain
visible in separate summaries.

Rust intent scores are uncalibrated heuristic scores, not probabilities.
Calibration labels are whether a formal tool call was actually emitted.
Calibration training and evaluation tasks must be disjoint; no calibrated
policy result will be reported unless both classes are present in training and
held-out tasks. No `theta*` decision rule will be applied to raw heuristic
scores.

## Deviations

Any deviation, missing factor, partial sample, or failed run is recorded in
the raw trace and reported. The report will state achieved sample counts and
will not imply that a preregistered target was achieved when it was not.

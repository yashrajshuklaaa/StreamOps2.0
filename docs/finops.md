# FinOps Threshold Prototype

> **Status: illustrative model, not validated cloud-cost optimization.** The current Go/Rust prototype uses hard-coded profile values and uncalibrated intent scores. It does not retrieve live prices, estimate remaining reasoning time, or establish that a trigger minimizes operational cost.

The equation below is a simplified expected-loss example. It assumes that `P_k` is a calibrated probability and that the listed costs accurately represent the decision. Those assumptions do not hold for the current prototype, so its threshold is heuristic rather than a proven optimal policy.

---

## Mathematical Derivation

Let tool $k$ have:
- $C_{\text{waste}}(k) = \text{cost\_per\_second} \times \text{TTL}$: Cost incurred if the speculative pod is created and discarded.
- $C_{\text{cold}}(k) = T_{\text{cold}} \times \mu_{\text{SLA}}$: Penalty incurred if the system fails to pre-warm and the user waits.
- $P_k = P(\text{Tool } k \mid \tau_{1:t})$: A calibrated probability would be required. The current detector's score is **not** such a probability.

### Expected Loss Comparison

$$\mathbb{E}[\text{Loss} \mid \text{Speculate}] = (1 - P_k) \cdot C_{\text{waste}}(k)$$
$$\mathbb{E}[\text{Loss} \mid \text{Wait}] = P_k \cdot C_{\text{cold}}(k)$$

Under those simplifying assumptions, the decision boundary would be:

$$(1 - P_k) C_{\text{waste}}(k) \le P_k C_{\text{cold}}(k)$$

$$\boxed{\theta^*(k) = \frac{C_{\text{waste}}(k)}{C_{\text{waste}}(k) + C_{\text{cold}}(k)}}$$

---

This equation omits the remaining reasoning window and the portion of cold-start time that could be hidden. It is not the lookahead-aware rule proposed for future work, nor an optimality result for the deployed implementation.

## Hard-coded prototype profiles

The following are source-code configuration values, not live provider prices or measured cold-start distributions. They are retained for prototype behavior and must not be used for a cloud budget or a performance claim.

| Tool | vCPU / RAM | Cost / sec | Cold Start ($T_{\text{cold}}$) | Waste Cost ($C_{\text{waste}}$) | Penalty ($C_{\text{cold}}$) | Optimal $\theta^*$ |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Python Sandbox** | 0.5 vCPU, 512MB | \$0.00005 | 5.5s | \$0.0030 | \$0.0275 | **0.15** (Eager) |
| **PostgreSQL DB** | 0.5 vCPU, 512MB | \$0.00008 | 6.0s | \$0.0048 | \$0.0300 | **0.15** (Eager) |
| **Chromium Browser** | 1.5 vCPU, 2GB | \$0.00020 | 8.0s | \$0.0120 | \$0.0400 | **0.23** (Moderate) |
| **Bash** | 0.25 vCPU, 256MB | \$0.00003 | 3.0s | \$0.0018 | \$0.0150 | **0.15** (clamped) |

No GPU profile or dynamic price integration is implemented. No claim is made that this policy minimizes spend, bounds expenditure, or improves latency. Calibration, current pricing inputs, lookahead-aware utility, and evaluation remain open work.

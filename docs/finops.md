# Bayesian FinOps Decision Theory

A central challenge in speculative cloud provisioning is **compute cost control**. If an agent speculatively provisions resources that are never used, cloud spend increases.

Stream-Ops solves this through a **Bayesian Cost-Utility Decision Policy**.

---

## Mathematical Derivation

Let tool $k$ have:
- $C_{\text{waste}}(k) = \text{cost\_per\_second} \times \text{TTL}$: Cost incurred if the speculative pod is created and discarded.
- $C_{\text{cold}}(k) = T_{\text{cold}} \times \mu_{\text{SLA}}$: Penalty incurred if the system fails to pre-warm and the user waits.
- $P_k = P(\text{Tool } k \mid \tau_{1:t})$: Cumulative intent confidence from streaming lookahead.

### Expected Loss Comparison

$$\mathbb{E}[\text{Loss} \mid \text{Speculate}] = (1 - P_k) \cdot C_{\text{waste}}(k)$$
$$\mathbb{E}[\text{Loss} \mid \text{Wait}] = P_k \cdot C_{\text{cold}}(k)$$

Speculation is optimal when $\mathbb{E}[\text{Loss} \mid \text{Speculate}] \le \mathbb{E}[\text{Loss} \mid \text{Wait}]$:

$$(1 - P_k) C_{\text{waste}}(k) \le P_k C_{\text{cold}}(k)$$

$$\boxed{\theta^*(k) = \frac{C_{\text{waste}}(k)}{C_{\text{waste}}(k) + C_{\text{cold}}(k)}}$$

---

## Default Tool FinOps Profiles

| Tool | vCPU / RAM | Cost / sec | Cold Start ($T_{\text{cold}}$) | Waste Cost ($C_{\text{waste}}$) | Penalty ($C_{\text{cold}}$) | Optimal $\theta^*$ |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Python Sandbox** | 0.5 vCPU, 512MB | \$0.00005 | 5.5s | \$0.0030 | \$0.0275 | **0.15** (Eager) |
| **PostgreSQL DB** | 0.5 vCPU, 512MB | \$0.00008 | 6.0s | \$0.0048 | \$0.0300 | **0.15** (Eager) |
| **Chromium Browser** | 1.5 vCPU, 2GB | \$0.00020 | 8.0s | \$0.0120 | \$0.0400 | **0.23** (Moderate) |
| **Heavy GPU Worker** | 4 vCPU, 16GB, GPU | \$0.00800 | 15.0s | \$0.4800 | \$0.0750 | **0.86** (Conservative) |

This dynamic boundary automatically ensures that **expensive GPU workloads require strict intent certainty**, while **lightweight CPU sandboxes trigger eagerly**, maximizing user speedups at minimal cost.

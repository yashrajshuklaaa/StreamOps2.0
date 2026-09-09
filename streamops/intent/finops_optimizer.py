from dataclasses import dataclass
from typing import Dict
import logging

logger = logging.getLogger("streamops.finops")

@dataclass
class ToolCostProfile:
    """FinOps cost parameters for a specific container sandbox tool."""
    tool_name: str
    cost_per_second_usd: float       # Compute cost (vCPU + RAM per second)
    cold_start_seconds: float        # Cold start latency (image pull + pod schedule + boot)
    latency_penalty_usd_per_sec: float # SLA penalty / cost value of 1 second of user wait time
    default_ttl_seconds: float = 60.0 # Time-To-Live before unclaimed pod is destroyed

    @property
    def cost_waste(self) -> float:
        """Cost wasted if pod is speculatively provisioned but discarded (False Positive)."""
        return self.cost_per_second_usd * self.default_ttl_seconds

    @property
    def cost_cold_start_penalty(self) -> float:
        """Cost penalty if pod is NOT pre-warmed and tool is invoked (False Negative)."""
        return self.cold_start_seconds * self.latency_penalty_usd_per_sec

    @property
    def optimal_threshold(self) -> float:
        """
        Bayesian Optimal Decision Threshold theta*:
        theta* = C_waste / (C_waste + C_cold)
        """
        c_waste = self.cost_waste
        c_cold = self.cost_cold_start_penalty
        denom = c_waste + c_cold
        if denom <= 0:
            return 0.5
        threshold = c_waste / denom
        # Clamp to realistic bounds [0.15, 0.90]
        return max(0.15, min(0.90, threshold))


class FinOpsOptimizer:
    """
    Manages FinOps profiles and computes Bayesian optimal decision thresholds
    to balance cloud infrastructure spend vs user latency reduction.
    """

    DEFAULT_PROFILES: Dict[str, ToolCostProfile] = {
        "python": ToolCostProfile(
            tool_name="python",
            cost_per_second_usd=0.00005,      # ~$0.18 / hour (0.5 vCPU, 512MB RAM)
            cold_start_seconds=5.5,           # ~5.5s pod startup
            latency_penalty_usd_per_sec=0.005 # Value of user time/SLA
        ),
        "sql": ToolCostProfile(
            tool_name="sql",
            cost_per_second_usd=0.00008,      # ~$0.28 / hour (Postgres instance)
            cold_start_seconds=6.0,
            latency_penalty_usd_per_sec=0.005
        ),
        "browser": ToolCostProfile(
            tool_name="browser",
            cost_per_second_usd=0.00020,      # ~$0.72 / hour (1.5 vCPU, 2GB RAM Chromium)
            cold_start_seconds=8.0,
            latency_penalty_usd_per_sec=0.005
        ),
        "bash": ToolCostProfile(
            tool_name="bash",
            cost_per_second_usd=0.00003,      # Lightweight alpine container
            cold_start_seconds=3.0,
            latency_penalty_usd_per_sec=0.005
        )
    }

    def __init__(self, custom_profiles: Dict[str, ToolCostProfile] = None):
        self.profiles: Dict[str, ToolCostProfile] = self.DEFAULT_PROFILES.copy()
        if custom_profiles:
            self.profiles.update(custom_profiles)

    def get_threshold(self, tool_name: str, base_threshold: float = 0.35) -> float:
        """Returns the Bayesian optimal threshold for a tool."""
        if tool_name in self.profiles:
            return self.profiles[tool_name].optimal_threshold
        return base_threshold

    def calculate_expected_utility(self, tool_name: str, confidence: float, speculate: bool) -> float:
        """
        Calculates expected loss E[Loss] given intent confidence P(tool).
        """
        profile = self.profiles.get(tool_name)
        if not profile:
            return 0.0

        p = confidence
        if speculate:
            # Speculating: If agent uses tool (p), loss = 0. If agent does not (1-p), loss = C_waste
            return (1.0 - p) * profile.cost_waste
        else:
            # Not speculating: If agent uses tool (p), loss = C_cold. If agent does not (1-p), loss = 0
            return p * profile.cost_cold_start_penalty

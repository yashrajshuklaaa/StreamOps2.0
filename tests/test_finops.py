import pytest
from streamops.intent.finops_optimizer import FinOpsOptimizer, ToolCostProfile

def test_finops_optimal_threshold():
    profile = ToolCostProfile(
        tool_name="python",
        cost_per_second_usd=0.00005,
        cold_start_seconds=5.5,
        latency_penalty_usd_per_sec=0.005,
        default_ttl_seconds=60.0
    )
    # C_waste = 0.00005 * 60 = 0.003
    # C_cold = 5.5 * 0.005 = 0.0275
    # theta* = 0.003 / (0.003 + 0.0275) = 0.003 / 0.0305 = ~0.098 -> clamped to min 0.15
    assert profile.cost_waste == pytest.approx(0.003)
    assert profile.cost_cold_start_penalty == pytest.approx(0.0275)
    assert profile.optimal_threshold >= 0.15

def test_finops_optimizer_profiles():
    optimizer = FinOpsOptimizer()
    assert "python" in optimizer.profiles
    assert "sql" in optimizer.profiles
    assert "browser" in optimizer.profiles

    python_thresh = optimizer.get_threshold("python")
    assert 0.15 <= python_thresh <= 0.90

def test_finops_expected_utility():
    optimizer = FinOpsOptimizer()
    # If confidence is 0.9 (high), loss of speculating is (1 - 0.9) * C_waste (very low)
    loss_spec = optimizer.calculate_expected_utility("python", confidence=0.9, speculate=True)
    loss_no_spec = optimizer.calculate_expected_utility("python", confidence=0.9, speculate=False)
    assert loss_spec < loss_no_spec

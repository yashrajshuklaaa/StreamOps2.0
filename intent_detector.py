"""
Legacy IntentDetector wrapper routing to streamops.intent.IntentDetector.
"""

from streamops.intent.detector import IntentDetector, IntentMatchResult
from streamops.intent.finops_optimizer import FinOpsOptimizer

__all__ = ["IntentDetector", "IntentMatchResult", "FinOpsOptimizer"]

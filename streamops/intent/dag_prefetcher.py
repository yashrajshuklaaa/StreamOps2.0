from typing import Dict, List, Optional
import logging

logger = logging.getLogger("streamops.dag_prefetcher")

class ToolDAGPrefetcher:
    """
    Predicts subsequent tool transitions across multi-step agent chains.
    Models transition probabilities: P(Tool_{t+1} | Tool_t).
    """

    DEFAULT_TRANSITIONS: Dict[str, Dict[str, float]] = {
        "sql": {
            "python": 0.85,    # After SQL query, 85% probability of analyzing in Python
            "browser": 0.10,
            "bash": 0.05
        },
        "python": {
            "browser": 0.45,   # After Python chart gen, 45% probability of browser/upload
            "sql": 0.20,
            "bash": 0.15
        },
        "browser": {
            "python": 0.70,    # After scraping, 70% probability of Python parsing
            "sql": 0.20,
            "bash": 0.10
        },
        "bash": {
            "python": 0.60,
            "sql": 0.20,
            "browser": 0.20
        }
    }

    def __init__(self, custom_transitions: Optional[Dict[str, Dict[str, float]]] = None):
        self.transitions = self.DEFAULT_TRANSITIONS.copy()
        if custom_transitions:
            self.transitions.update(custom_transitions)

    def predict_next_tools(self, current_tool: str, min_probability: float = 0.5) -> List[str]:
        """Returns candidate next tools that exceed the minimum transition probability."""
        if current_tool not in self.transitions:
            return []

        candidates = []
        for next_tool, prob in self.transitions[current_tool].items():
            if prob >= min_probability:
                candidates.append(next_tool)

        return candidates

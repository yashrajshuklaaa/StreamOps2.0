import time
from enum import Enum
from dataclasses import dataclass
from typing import Optional

class SpeculationState(str, Enum):
    IDLE = "IDLE"
    LOOKAHEAD = "LOOKAHEAD"
    SPECULATING = "SPECULATING"
    PREWARMED = "PREWARMED"
    CLAIMED = "CLAIMED"
    RECLAIMED = "RECLAIMED"
    ROLLEDBACK = "ROLLEDBACK"

@dataclass
class SpeculationSession:
    session_id: str
    tool_name: Optional[str] = None
    state: SpeculationState = SpeculationState.IDLE
    confidence: float = 0.0
    start_time: float = 0.0
    trigger_time: float = 0.0
    ready_time: float = 0.0
    claim_time: float = 0.0
    pod_name: Optional[str] = None

    @property
    def latency_masked(self) -> float:
        """Returns the time saved (seconds) by pre-warming in parallel."""
        if self.trigger_time > 0 and self.claim_time > 0:
            if self.ready_time > 0 and self.ready_time <= self.claim_time:
                # Pod was ready before tool call: 100% cold start was masked!
                return self.ready_time - self.trigger_time
            elif self.ready_time > 0 and self.ready_time > self.claim_time:
                # Partial mask: pod was still starting when tool call arrived
                return self.claim_time - self.trigger_time
        return 0.0

class SpeculationStateMachine:
    """Tracks state transitions for speculative sandbox sessions."""

    def __init__(self, session_id: str):
        self.session = SpeculationSession(
            session_id=session_id,
            start_time=time.time()
        )

    def transition_to_lookahead(self, confidence: float):
        if self.session.state == SpeculationState.IDLE:
            self.session.state = SpeculationState.LOOKAHEAD
        self.session.confidence = confidence

    def transition_to_speculating(self, tool_name: str, pod_name: str, confidence: float):
        self.session.state = SpeculationState.SPECULATING
        self.session.tool_name = tool_name
        self.session.pod_name = pod_name
        self.session.confidence = confidence
        self.session.trigger_time = time.time()

    def transition_to_prewarmed(self):
        if self.session.state == SpeculationState.SPECULATING:
            self.session.state = SpeculationState.PREWARMED
            self.session.ready_time = time.time()

    def transition_to_claimed(self) -> float:
        self.session.state = SpeculationState.CLAIMED
        self.session.claim_time = time.time()
        return self.session.latency_masked

    def transition_to_reclaimed(self):
        self.session.state = SpeculationState.RECLAIMED

    def transition_to_rolled_back(self):
        self.session.state = SpeculationState.ROLLEDBACK

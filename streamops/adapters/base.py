from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
import logging

logger = logging.getLogger("streamops.adapters")

@dataclass
class StreamChunk:
    """Represents a normalized streaming token or reasoning chunk."""
    text: str
    is_reasoning: bool = False
    is_tool_call: bool = False
    tool_name: Optional[str] = None
    tool_args: Optional[str] = None
    is_done: bool = False
    raw_payload: Optional[Dict[str, Any]] = None

class StreamingAdapter(ABC):
    """
    Abstract base class for provider-agnostic LLM streaming normalization.
    Decouples raw network bytes (SSE, NDJSON, WebSocket) into normalized StreamChunk events.
    """

    @abstractmethod
    def parse_chunk(self, chunk: bytes) -> List[StreamChunk]:
        """Parses raw byte chunks from the LLM provider and returns normalized chunks."""
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        """Returns the human-readable name of the provider adapter."""
        pass

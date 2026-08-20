import json
import logging
from abc import ABC, abstractmethod
from typing import AsyncGenerator, Optional

logger = logging.getLogger("Adapters")

class StreamingAdapter(ABC):
    """
    Abstract base class for LLM Streaming Adapters.
    Converts provider-specific streaming chunks into a common format (raw text).
    """
    @abstractmethod
    def parse_chunk(self, chunk: bytes) -> str:
        """Parses a byte chunk from the LLM stream and returns the extracted text."""
        pass


class OllamaAdapter(StreamingAdapter):
    """Parses Ollama's NDJSON streaming format."""
    
    def parse_chunk(self, chunk: bytes) -> str:
        text_chunk = chunk.decode("utf-8", errors="ignore").strip()
        buffer = ""
        lines = text_chunk.split('\n')
        for line in lines:
            if line:
                try:
                    data = json.loads(line)
                    if "response" in data:
                        buffer += data["response"]
                    elif "message" in data and "content" in data["message"]:
                        # Chat completion format
                        buffer += data["message"]["content"]
                except json.JSONDecodeError:
                    pass
        return buffer


class OpenAIAdapter(StreamingAdapter):
    """Parses OpenAI's Server-Sent Events (SSE) streaming format."""
    
    def parse_chunk(self, chunk: bytes) -> str:
        text_chunk = chunk.decode("utf-8", errors="ignore").strip()
        buffer = ""
        lines = text_chunk.split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith("data: "):
                data_str = line[6:]
                if data_str == "[DONE]":
                    continue
                try:
                    data = json.loads(data_str)
                    if "choices" in data and len(data["choices"]) > 0:
                        delta = data["choices"][0].get("delta", {})
                        if "content" in delta and delta["content"]:
                            buffer += delta["content"]
                except json.JSONDecodeError:
                    pass
        return buffer


def get_adapter(model_name: str) -> StreamingAdapter:
    """Factory to get the correct adapter based on the model name."""
    model_name = model_name.lower()
    if "gpt" in model_name or "openai" in model_name:
        return OpenAIAdapter()
    # Default to Ollama for the POC
    return OllamaAdapter()

import re
from typing import List
from .base import StreamingAdapter, StreamChunk
from .ollama import OllamaAdapter
from .openai import OpenAIAdapter

class DeepSeekAdapter(StreamingAdapter):
    """
    Specialized adapter for DeepSeek R1 & reasoning models that emit `<think> ... </think>` tags.
    Tracks whether current tokens are internal reasoning (Chain-of-Thought) or user-facing output.
    """

    def __init__(self, fallback_format: str = "ollama"):
        self.fallback_format = fallback_format
        self.underlying_adapter = OllamaAdapter() if fallback_format == "ollama" else OpenAIAdapter()
        self.in_think_block = False

    def parse_chunk(self, chunk: bytes) -> List[StreamChunk]:
        raw_chunks = self.underlying_adapter.parse_chunk(chunk)
        processed: List[StreamChunk] = []

        for c in raw_chunks:
            text = c.text
            
            # Check for <think> opening tag
            if "<think>" in text:
                self.in_think_block = True
                text = text.replace("<think>", "")

            # Check for </think> closing tag
            if "</think>" in text:
                self.in_think_block = False
                text = text.replace("</think>", "")

            # Mark chunk as reasoning if currently inside <think> tag or already flagged
            is_reasoning = self.in_think_block or c.is_reasoning

            processed.append(
                StreamChunk(
                    text=text,
                    is_reasoning=is_reasoning,
                    is_tool_call=c.is_tool_call,
                    tool_name=c.tool_name,
                    tool_args=c.tool_args,
                    is_done=c.is_done,
                    raw_payload=c.raw_payload
                )
            )

        return processed

    def get_provider_name(self) -> str:
        return f"DeepSeek R1 Lookahead ({self.underlying_adapter.get_provider_name()})"

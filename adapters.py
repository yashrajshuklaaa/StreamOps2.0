"""
Legacy Adapters wrapper routing to streamops.adapters.
"""

from streamops.adapters.base import StreamingAdapter, StreamChunk
from streamops.adapters.ollama import OllamaAdapter
from streamops.adapters.openai import OpenAIAdapter
from streamops.adapters.anthropic import AnthropicAdapter
from streamops.adapters.deepseek import DeepSeekAdapter
from streamops.adapters.factory import get_adapter

__all__ = [
    "StreamingAdapter",
    "StreamChunk",
    "OllamaAdapter",
    "OpenAIAdapter",
    "AnthropicAdapter",
    "DeepSeekAdapter",
    "get_adapter",
]

from typing import Optional
from .base import StreamingAdapter
from .ollama import OllamaAdapter
from .openai import OpenAIAdapter
from .anthropic import AnthropicAdapter
from .deepseek import DeepSeekAdapter

def get_adapter(model_name: str, provider_hint: Optional[str] = None) -> StreamingAdapter:
    """
    Factory to return the optimal streaming adapter based on model name and provider hint.
    """
    model_lower = model_name.lower() if model_name else ""
    hint_lower = provider_hint.lower() if provider_hint else ""

    if "deepseek" in model_lower or "r1" in model_lower:
        fallback = "openai" if ("openai" in hint_lower or "vllm" in hint_lower) else "ollama"
        return DeepSeekAdapter(fallback_format=fallback)

    if "claude" in model_lower or "anthropic" in hint_lower:
        return AnthropicAdapter()

    if "gpt" in model_lower or "o1" in model_lower or "o3" in model_lower or "openai" in hint_lower or "vllm" in hint_lower:
        return OpenAIAdapter()

    # Default to Ollama format for local/open-source models
    return OllamaAdapter()

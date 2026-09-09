import pytest
import json
from streamops.adapters.base import StreamChunk
from streamops.adapters.ollama import OllamaAdapter
from streamops.adapters.openai import OpenAIAdapter
from streamops.adapters.anthropic import AnthropicAdapter
from streamops.adapters.deepseek import DeepSeekAdapter
from streamops.adapters.factory import get_adapter

def test_ollama_adapter_parse_generate():
    adapter = OllamaAdapter()
    raw = json.dumps({"model": "llama3", "response": "Hello world", "done": False}).encode("utf-8")
    chunks = adapter.parse_chunk(raw)
    assert len(chunks) == 1
    assert chunks[0].text == "Hello world"
    assert not chunks[0].is_done

def test_ollama_adapter_parse_done():
    adapter = OllamaAdapter()
    raw = json.dumps({"model": "llama3", "response": "", "done": True}).encode("utf-8")
    chunks = adapter.parse_chunk(raw)
    assert len(chunks) == 1
    assert chunks[0].is_done

def test_openai_adapter_sse():
    adapter = OpenAIAdapter()
    sse_data = (
        b"data: {\"choices\": [{\"delta\": {\"content\": \"Let's analyze\"}}]}\n\n"
        b"data: [DONE]\n\n"
    )
    chunks = adapter.parse_chunk(sse_data)
    assert len(chunks) == 2
    assert chunks[0].text == "Let's analyze"
    assert not chunks[0].is_done
    assert chunks[1].is_done

def test_deepseek_think_lookahead():
    adapter = DeepSeekAdapter(fallback_format="ollama")
    chunk1 = json.dumps({"response": "<think>I need to write a script"}).encode("utf-8")
    chunk2 = json.dumps({"response": " using python.</think>Done."}).encode("utf-8")
    
    res1 = adapter.parse_chunk(chunk1)
    assert len(res1) == 1
    assert res1[0].is_reasoning is True
    assert "I need to write a script" in res1[0].text

    res2 = adapter.parse_chunk(chunk2)
    assert len(res2) == 1
    assert "using python." in res2[0].text

def test_adapter_factory():
    assert isinstance(get_adapter("deepseek-r1"), DeepSeekAdapter)
    assert isinstance(get_adapter("gpt-4o"), OpenAIAdapter)
    assert isinstance(get_adapter("claude-3-5-sonnet"), AnthropicAdapter)
    assert isinstance(get_adapter("llama3"), OllamaAdapter)

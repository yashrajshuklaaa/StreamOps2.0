import json
from typing import List
from .base import StreamingAdapter, StreamChunk

class OllamaAdapter(StreamingAdapter):
    """Parses Ollama's Newline-Delimited JSON (NDJSON) streaming format."""

    def parse_chunk(self, chunk: bytes) -> List[StreamChunk]:
        results: List[StreamChunk] = []
        text_data = chunk.decode("utf-8", errors="ignore").strip()
        lines = text_data.split("\n")

        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                is_done = data.get("done", False)
                
                # Check for generate endpoint
                if "response" in data:
                    content = data["response"]
                    if content or is_done:
                        results.append(StreamChunk(text=content, is_done=is_done, raw_payload=data))
                # Check for chat endpoint
                elif "message" in data and "content" in data["message"]:
                    content = data["message"]["content"]
                    tool_calls = data["message"].get("tool_calls", [])
                    is_tool = len(tool_calls) > 0
                    tool_name = tool_calls[0].get("function", {}).get("name") if is_tool else None
                    results.append(
                        StreamChunk(
                            text=content,
                            is_done=is_done,
                            is_tool_call=is_tool,
                            tool_name=tool_name,
                            raw_payload=data
                        )
                    )
                elif is_done:
                    results.append(StreamChunk(text="", is_done=True, raw_payload=data))
            except json.JSONDecodeError:
                pass

        return results

    def get_provider_name(self) -> str:
        return "Ollama (NDJSON)"

import json
from typing import List
from .base import StreamingAdapter, StreamChunk

class AnthropicAdapter(StreamingAdapter):
    """
    Parses Anthropic Claude SSE format (content_block_delta, thinking_delta, message_stop).
    """

    def parse_chunk(self, chunk: bytes) -> List[StreamChunk]:
        results: List[StreamChunk] = []
        text_data = chunk.decode("utf-8", errors="ignore").strip()
        lines = text_data.split("\n")

        for line in lines:
            line = line.strip()
            if not line.startswith("data:"):
                continue

            data_str = line[5:].strip()
            if not data_str:
                continue

            try:
                data = json.loads(data_str)
                event_type = data.get("type", "")

                if event_type == "content_block_delta":
                    delta = data.get("delta", {})
                    delta_type = delta.get("type", "")
                    
                    if delta_type == "text_delta":
                        results.append(StreamChunk(text=delta.get("text", ""), is_reasoning=False, raw_payload=data))
                    elif delta_type == "thinking_delta":
                        results.append(StreamChunk(text=delta.get("thinking", ""), is_reasoning=True, raw_payload=data))
                    elif delta_type == "input_json_delta":
                        results.append(StreamChunk(text=delta.get("partial_json", ""), is_tool_call=True, raw_payload=data))

                elif event_type == "message_stop":
                    results.append(StreamChunk(text="", is_done=True, raw_payload=data))
            except json.JSONDecodeError:
                pass

        return results

    def get_provider_name(self) -> str:
        return "Anthropic Claude (SSE)"

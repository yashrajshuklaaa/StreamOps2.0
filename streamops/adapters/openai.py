import json
from typing import List
from .base import StreamingAdapter, StreamChunk

class OpenAIAdapter(StreamingAdapter):
    """
    Parses OpenAI Server-Sent Events (SSE) streaming format (`data: {...}`).
    Handles text tokens, tool calls, and reasoning tokens (o1/o3/DeepSeek style).
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
            if data_str == "[DONE]":
                results.append(StreamChunk(text="", is_done=True))
                continue

            try:
                data = json.loads(data_str)
                choices = data.get("choices", [])
                if not choices:
                    continue

                delta = choices[0].get("delta", {})
                finish_reason = choices[0].get("finish_reason")
                is_done = finish_reason is not None

                # 1. Check reasoning content (OpenAI o-series / DeepSeek R1 API)
                if "reasoning_content" in delta and delta["reasoning_content"]:
                    results.append(
                        StreamChunk(
                            text=delta["reasoning_content"],
                            is_reasoning=True,
                            is_done=is_done,
                            raw_payload=data
                        )
                    )

                # 2. Check standard content delta
                if "content" in delta and delta["content"]:
                    results.append(
                        StreamChunk(
                            text=delta["content"],
                            is_reasoning=False,
                            is_done=is_done,
                            raw_payload=data
                        )
                    )

                # 3. Check tool calls
                if "tool_calls" in delta and delta["tool_calls"]:
                    tool_call = delta["tool_calls"][0]
                    func = tool_call.get("function", {})
                    tool_name = func.get("name")
                    tool_args = func.get("arguments")
                    results.append(
                        StreamChunk(
                            text="",
                            is_tool_call=True,
                            tool_name=tool_name,
                            tool_args=tool_args,
                            is_done=is_done,
                            raw_payload=data
                        )
                    )
            except json.JSONDecodeError:
                pass

        return results

    def get_provider_name(self) -> str:
        return "OpenAI (SSE)"

import asyncio
import json
import pytest
from httpx import AsyncClient, ASGITransport
import httpx
from stream_proxy import app, trigger_k8s_provisioning

@pytest.mark.asyncio
async def test_proxy_intercepts_intent(mocker):
    # Mock the trigger function so we can assert it was called
    mock_trigger = mocker.patch("stream_proxy.trigger_k8s_provisioning", return_value=None)
    
    # Mock Ollama's response stream
    async def mock_stream_response():
        words = ["I", " will", " use", " python", " now."]
        for w in words:
            yield json.dumps({"response": w}).encode("utf-8") + b"\n"
            
    # Mock the httpx AsyncClient in stream_proxy
    class MockResponse:
        def __init__(self):
            self.status_code = 200
        async def aiter_bytes(self):
            async for chunk in mock_stream_response():
                yield chunk
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    class MockClient:
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass
        def stream(self, method, url, **kwargs):
            return MockResponse()

    mocker.patch("stream_proxy.httpx.AsyncClient", return_value=MockClient())

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/generate", json={"prompt": "test"})
        
        # Consume the stream
        chunks = []
        async for chunk in response.aiter_bytes():
            chunks.append(chunk)
            
        assert response.status_code == 200
        assert len(chunks) > 0
        
        # Ensure our mock trigger was called because 'python' was in the stream
        mock_trigger.assert_called_once()

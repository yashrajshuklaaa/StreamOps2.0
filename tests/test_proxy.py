import asyncio
import json
import pytest
from httpx import AsyncClient, ASGITransport
from streamops.proxy.server import app

@pytest.mark.asyncio
async def test_proxy_healthz():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/healthz")
        assert res.status_code == 200
        assert res.json()["status"] == "ok"

@pytest.mark.asyncio
async def test_proxy_metrics():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/metrics")
        assert res.status_code == 200
        assert "streamops_tokens_processed_total" in res.text

@pytest.mark.asyncio
async def test_proxy_intercepts_intent(mocker):
    # Mock the trigger function
    mock_trigger = mocker.patch("streamops.proxy.server.trigger_k8s_provisioning", return_value=None)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Send prompt with python/pandas keyword
        payload = {
            "model": "llama3",
            "prompt": "I need to analyze this data. Let me write a python pandas script now.",
            "stream": True
        }
        response = await client.post("/api/generate", json=payload)
        assert response.status_code == 200

        chunks = []
        async for chunk in response.aiter_bytes():
            chunks.append(chunk)

        assert len(chunks) > 0
        # Wait slightly for background task invocation
        await asyncio.sleep(0.05)
        assert mock_trigger.called

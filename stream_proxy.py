import asyncio
import json
import logging
from fastapi import FastAPI, Request, Response
from fastapi.responses import StreamingResponse
import httpx
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

from k8s_provisioner import warmup_tool_pod, cleanup_unused_pods
from adapters import get_adapter
from intent_detector import IntentDetector

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("StreamProxy")

app = FastAPI(title="Stream-Ops Semantic Proxy")

OLLAMA_URL = "http://localhost:11434/api/generate"

OLLAMA_URL = "http://localhost:11434/api/generate"

# Prometheus Metrics
INTENT_DETECTED = Counter('streamops_intents_detected_total', 'Total number of infrastructure intents detected', ['tool'])
POD_WARMUP_LATENCY = Histogram('streamops_pod_warmup_seconds', 'Latency of warming up a pod')

async def garbage_collection_loop():
    while True:
        await asyncio.sleep(30)
        logger.info("Running pod garbage collection (TTL 60s)...")
        await asyncio.to_thread(cleanup_unused_pods, ttl_seconds=60)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(garbage_collection_loop())

async def trigger_k8s_provisioning(tool_name: str):
    """Background task to trigger K8s pod creation."""
    logger.info(f"⚡ STREAM-OPS DETECTED INTENT: {tool_name.upper()}! Triggering K8s Pod Create ⚡")
    INTENT_DETECTED.labels(tool=tool_name).inc()
    
    import time
    start = time.time()
    # Run the synchronous K8s client call in a thread pool to avoid blocking the async event loop
    await asyncio.to_thread(warmup_tool_pod, tool_name)
    POD_WARMUP_LATENCY.observe(time.time() - start)

@app.get("/metrics")
async def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.post("/api/generate")
async def proxy_generate(request: Request):
    """
    Proxies the request to Ollama and streams the response back.
    Uses generic adapters and intent detectors to trigger infrastructure.
    """
    req_body = await request.json()
    model_name = req_body.get("model", "llama3")
    
    # Instantiate the components for this request
    adapter = get_adapter(model_name)
    detector = IntentDetector(threshold=0.8)
    
    async def stream_generator():
        async with httpx.AsyncClient() as client:
            try:
                # In a real implementation, you'd route to OLLAMA_URL or OPENAI_URL based on the adapter/model.
                # Here we continue to forward to Ollama for the POC.
                async with client.stream("POST", OLLAMA_URL, json=req_body, timeout=60.0) as response:
                    async for chunk in response.aiter_bytes():
                        if chunk:
                            # 1. Adapter parses raw bytes into text
                            text_chunk = adapter.parse_chunk(chunk)
                            
                            if text_chunk:
                                # 2. Detector analyzes text for intent
                                triggered_tool = detector.process_chunk(text_chunk)
                                
                                # 3. Trigger K8s if confidence threshold is met
                                if triggered_tool:
                                    asyncio.create_task(trigger_k8s_provisioning(triggered_tool))
                                    
                            yield chunk
            except httpx.ConnectError:
                logger.error("Could not connect to LLM Provider.")
                yield json.dumps({"error": "LLM Provider is down"}).encode("utf-8")
                        
    return StreamingResponse(stream_generator(), media_type="application/x-ndjson")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

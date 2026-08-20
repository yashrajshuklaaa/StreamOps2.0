import asyncio
import json
import logging
from fastapi import FastAPI, Request, Response
from fastapi.responses import StreamingResponse
import httpx
import re
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

from k8s_provisioner import warmup_tool_pod, cleanup_unused_pods

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("StreamProxy")

app = FastAPI(title="Stream-Ops Semantic Proxy")

OLLAMA_URL = "http://localhost:11434/api/generate"

# Dictionary to map regex patterns to specific tool pods
INTENT_PATTERNS = {
    "python": re.compile(r"(python|execute_code|pandas|script)", re.IGNORECASE),
    "sql": re.compile(r"(sql|postgres|database|query)", re.IGNORECASE),
    "browser": re.compile(r"(search|browser|webpage|scrape)", re.IGNORECASE)
}

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
    Proxies the request to Ollama and streams the response back,
    inspecting the stream in real-time for infrastructure hints.
    """
    req_body = await request.json()
    
    async def stream_generator():
        triggered = False
        buffer = ""
        
        async with httpx.AsyncClient() as client:
            try:
                async with client.stream("POST", OLLAMA_URL, json=req_body, timeout=60.0) as response:
                    async for chunk in response.aiter_bytes():
                        if chunk:
                            # Decode chunk to inspect
                            text_chunk = chunk.decode("utf-8", errors="ignore")
                            
                            # Try parsing Ollama's JSON response
                            try:
                                # Ollama streams JSON objects separated by newlines
                                lines = text_chunk.strip().split('\n')
                                for line in lines:
                                    if line:
                                        data = json.loads(line)
                                        word = data.get("response", "")
                                        buffer += word
                                        
                                        # Check for intent if not already triggered
                                        if not triggered:
                                            for tool, pattern in INTENT_PATTERNS.items():
                                                if pattern.search(buffer):
                                                    triggered = True
                                                    asyncio.create_task(trigger_k8s_provisioning(tool))
                                                    break
                            except json.JSONDecodeError:
                                pass # Incomplete JSON chunk, will process on next chunk
                                
                            yield chunk
            except httpx.ConnectError:
                logger.error("Could not connect to Ollama. Make sure it is running on http://localhost:11434")
                yield json.dumps({"error": "Ollama is not running"}).encode("utf-8")
                        
    return StreamingResponse(stream_generator(), media_type="application/x-ndjson")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

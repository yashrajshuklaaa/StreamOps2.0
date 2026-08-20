import asyncio
import json
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse

app = FastAPI()

dummy_response_text = [
    "I ", "need ", "to ", "use ", "the ", "python ", "tool ", "to ", "analyze ", "the ", "dataset. ",
    "Let ", "me ", "import ", "pandas ", "and ", "load ", "the ", "data. ",
    "Wait, ", "first ", "I ", "will ", "use ", "the ", "python_repl ", "to ", "do ", "this."
]

@app.post("/api/generate")
async def dummy_generate(request: Request):
    async def stream_generator():
        for word in dummy_response_text:
            data = {"model": "llama3:8b", "response": word, "done": False}
            yield json.dumps(data) + "\n"
            await asyncio.sleep(0.3)  # Simulate streaming delay
        
        yield json.dumps({"model": "llama3:8b", "response": "", "done": True}) + "\n"
        
    return StreamingResponse(stream_generator(), media_type="application/x-ndjson")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=11434)

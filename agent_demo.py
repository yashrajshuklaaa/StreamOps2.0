import asyncio
import httpx
import time
import json
from rich.console import Console
from rich.panel import Panel

console = Console()

PROXY_URL = "http://localhost:8000/api/generate"

PROMPT = """
You are an AI assistant. I have a dataset of 1000 users. 
I need to analyze it. Think out loud about the steps you will take, 
and then specify that you will write a python script using pandas.
"""

async def run_demo():
    console.print(Panel.fit("[bold green]Stream-Ops Demonstration[/bold green]", border_style="green"))
    console.print(f"[bold cyan]0.0s[/bold cyan] --- User Submits Prompt")
    start_time = time.time()
    
    req_body = {
        "model": "llama3:8b", # Make sure you have this model pulled in Ollama
        "prompt": PROMPT,
        "stream": True
    }
    
    async with httpx.AsyncClient() as client:
        try:
            async with client.stream("POST", PROXY_URL, json=req_body, timeout=120.0) as response:
                first_token = True
                
                async for chunk in response.aiter_bytes():
                    if chunk:
                        lines = chunk.decode("utf-8", errors="ignore").strip().split('\n')
                        for line in lines:
                            if line:
                                try:
                                    data = json.loads(line)
                                    if "error" in data:
                                        console.print(f"\n[bold red]Proxy Error: {data['error']}[/bold red]")
                                        return
                                    word = data.get("response", "")
                                    if first_token and word:
                                        elapsed = time.time() - start_time
                                        console.print(f"[bold cyan]{elapsed:.1f}s[/bold cyan] --- LLM starts generating Chain-of-Thought (CoT)")
                                        first_token = False
                                        
                                    # Print the thinking process (without newline for streaming effect)
                                    print(word, end="", flush=True)
                                except json.JSONDecodeError:
                                    pass
        except httpx.ConnectError:
            console.print("\n[bold red]Error: Could not connect to Proxy. Is stream_proxy.py running on port 8000?[/bold red]")
            return

    print("\n")
    elapsed = time.time() - start_time
    console.print(f"\n[bold cyan]{elapsed:.1f}s[/bold cyan] --- LLM completes thought.")
    
    console.print("\n[bold yellow]In a traditional system, we would NOW start the Python Pod (5-10s delay).[/bold yellow]")
    console.print("[bold green]With Stream-Ops, the Pod was started during the CoT phase and is already HOT![/bold green]\n")

if __name__ == "__main__":
    asyncio.run(run_demo())

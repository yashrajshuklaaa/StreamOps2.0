# Stream-Ops: Just-in-Time Kubernetes Provisioning via Chain-of-Thought Lookahead

This is a proof-of-concept for the "Stream-Ops" Capstone project. It demonstrates how to exploit the semantic window of an LLM's Chain-of-Thought (CoT) generation to pre-warm infrastructure (like a Kubernetes Pod) before the final tool call is actually made.

## Architecture

1.  **LLM**: Locally hosted `Ollama` running models like `llama3:8b`.
2.  **Semantic Proxy**: A FastAPI application (`stream_proxy.py`) that intercepts the LLM stream, buffering tokens and using regex to detect infrastructure intent (e.g., "python" or "pandas").
3.  **K8s Provisioner**: A Python script (`k8s_provisioner.py`) utilizing the official Kubernetes client to spin up a Docker container in a local Minikube cluster as soon as intent is detected.
4.  **Client Simulator**: A script (`agent_demo.py`) that acts as the UI/User, demonstrating the timeline in the console.

## Setup Instructions

### 1. Prerequisites
- Python 3.9+
- Docker
- [Minikube](https://minikube.sigs.k8s.io/docs/start/)
- [Ollama](https://ollama.com/)

### 2. Install Python Dependencies
```bash
pip install -r requirements.txt
```

### 3. Start Minikube
```bash
minikube start
```

### 4. Start Ollama
Ensure Ollama is running and you have downloaded a model (e.g., `llama3:8b`).
```bash
ollama run llama3:8b
# Ollama runs on http://localhost:11434 by default.
```

### 5. Run the Semantic Proxy
In one terminal, start the FastAPI proxy. This will listen on port 8000 and forward requests to Ollama.
```bash
python stream_proxy.py
```

### 6. Run the Demo Agent
In another terminal, run the agent script to see Stream-Ops in action:
```bash
python agent_demo.py
```

## How it works (The Patent Novelty)

Watch the logs in the `stream_proxy.py` terminal. 
When the agent starts generating its internal monologue (Chain-of-Thought) and mentions a keyword like **"python"** or **"pandas"**, the proxy will instantly detect it.

While the LLM is *still streaming* the rest of its response, the proxy fires the Kubernetes Pod creation command in the background.

By the time the LLM finishes responding (which usually takes 3-10 seconds), the Kubernetes pod is already `Running` and ready to execute the code! 

This completely eliminates the 5-10 second "Cold Start" delay typically associated with launching heavy agent tools like isolated sandboxes.

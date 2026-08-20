# Getting Started

This guide will help you set up and run the Stream-Ops proxy and the visual demonstration.

## Prerequisites
- Python 3.9+
- Kubernetes cluster (e.g., Minikube or Docker Desktop with Kubernetes enabled)
- (Optional) Ollama running locally for the POC simulation

## Installation

1. Clone the repository and navigate to the project directory:
   ```bash
   git clone https://github.com/your-username/stream-ops.git
   cd stream-ops
   ```

2. Install the required Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Running the Proxy

Stream-Ops acts as a transparent middleware. Start the FastAPI proxy server:

```bash
python stream_proxy.py
```
*The proxy will run on `http://localhost:8000`.*

## Running the End-to-End Demo

We have provided a simulation script that demonstrates how Stream-Ops detects intents and saves latency.

In a separate terminal, run:
```bash
python dummy_ollama.py   # Starts a simulated LLM on port 11434
python agent_demo.py     # Runs the interactive benchmark
```

## Running the Tests

To verify that the proxy and Kubernetes provisioning logic are functioning correctly:
```bash
pytest tests/
```

## Viewing Metrics

Stream-Ops exposes standard Prometheus metrics. While the proxy is running, you can view the metrics at:
```bash
curl http://localhost:8000/metrics
```

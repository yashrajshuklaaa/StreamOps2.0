#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

kind create cluster --config deploy/kind/kind-cluster.yaml

docker build -t streamops/intent-engine:local -f services/intent-engine/Dockerfile services/intent-engine
docker build -t streamops/control-plane:local -f services/control-plane/Dockerfile services/control-plane

kind load docker-image streamops/intent-engine:local --name streamops
kind load docker-image streamops/control-plane:local --name streamops

kubectl apply -f deploy/kind/streamops.yaml
kubectl apply -f deploy/kind/ollama.yaml
kubectl rollout status deployment/intent-engine -n streamops --timeout=120s
kubectl rollout status deployment/control-plane -n streamops --timeout=120s

echo "StreamOps control plane: http://localhost:8000"
echo "Metrics:                 http://localhost:8000/metrics"

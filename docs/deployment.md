# Deployment

## Local Kind prototype

The Go control plane and Rust intent service can be built and deployed to a
local Kind cluster using:

```bash
./scripts/run-kind.sh
```

The script creates a `streamops` Kind cluster, builds and loads the two service
images, then deploys the services and Ollama. The local cluster exposes the Go
service on `http://localhost:8000`. The repository
[README](https://github.com/yashrajshuklaaa/StreamOps2.0/blob/main/README.md)
has a streaming smoke-test request.

The setup uses real Kubernetes pods, but does not execute tool payloads or
represent a production deployment. The Ollama model must be downloaded
separately, and cluster behavior depends on local machine resources and image
availability.

## Legacy deployment examples

`deploy/docker-compose.yml`, `deploy/helm/stream-ops/`, and
`deploy/terraform/` predate the Go/Rust prototype. They describe examples for
the legacy Python stack and have not been validated as deployment artifacts
for the current services. The Helm chart and Terraform files must not be
treated as production-ready infrastructure without review and testing.

The Go/Rust prototype does not yet include a Kubernetes operator, CRD-based
reconciliation, production RBAC policy, NetworkPolicy, priority/preemption
configuration, or a production observability deployment.

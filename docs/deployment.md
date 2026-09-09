# Cloud DevOps & Deployment Guide

Stream-Ops is designed to run seamlessly from local development to multi-region cloud Kubernetes clusters.

---

## 1. Local Development (Docker Compose)

The easiest way to run the entire Stream-Ops stack (Control Plane + Mock LLM + Prometheus + Grafana + Redis + Jaeger) locally:

```bash
cd deploy
docker-compose up --build
```

### Endpoints:
- **Stream-Ops Visualizer Dashboard**: [http://localhost:8000/dashboard](http://localhost:8000/dashboard)
- **Prometheus Metrics**: [http://localhost:9090](http://localhost:9090)
- **Grafana Dashboard**: [http://localhost:3000](http://localhost:3000) (User: `admin`, Pass: `admin`)
- **Jaeger Distributed Traces**: [http://localhost:16686](http://localhost:16686)

---

## 2. Production Kubernetes Deployment (Helm v3)

### Step 1: Install Custom Resource Definitions (CRDs)
```bash
kubectl apply -f streamops/k8s/crd/
```

### Step 2: Deploy Helm Chart
```bash
helm upgrade --install stream-ops deploy/helm/stream-ops \
  --namespace streamops-system \
  --create-namespace \
  --set replicaCount=3 \
  --set env.OLLAMA_URL="http://ollama.ai.svc.cluster.local:11434/api/generate"
```

---

## 3. Infrastructure as Code (Terraform for AWS EKS)

```bash
cd deploy/terraform
terraform init
terraform plan -out=tfplan
terraform apply tfplan
```

This provisions:
- Production AWS VPC with public/private subnets.
- Amazon EKS Cluster v1.28 with Spot and On-Demand Node Groups.
- IAM Roles for Service Accounts (IRSA) for Kubernetes Pod management.

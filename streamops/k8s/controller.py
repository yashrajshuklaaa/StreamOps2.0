import json
import logging
import os
import time
import uuid
from dataclasses import dataclass
from typing import Optional, Dict, Any, List

from .mock_cluster import MockKubernetesCluster

logger = logging.getLogger("streamops.k8s")

try:
    from kubernetes import client, config
    from kubernetes.client.rest import ApiException
    K8S_AVAILABLE = True
except ImportError:
    K8S_AVAILABLE = False
    logger.warning("Kubernetes Python client not installed. Falling back to MockKubernetesCluster.")

@dataclass
class PodProvisionResult:
    success: bool
    pod_name: str
    tool_name: str
    namespace: str
    is_mock: bool
    status: str
    created_at: float

class KubernetesSandboxController:
    """
    Enterprise Kubernetes Controller for speculative sandbox lifecycle management.
    Handles Just-In-Time pod creation, session isolation, warm pool reservations,
    and automatic TTL garbage collection.
    """

    def __init__(self, registry_path: str = "tools_registry.json", namespace: str = "default", fallback_to_mock: bool = True):
        self.registry_path = registry_path
        self.namespace = namespace
        self.fallback_to_mock = fallback_to_mock
        self.mock_cluster = MockKubernetesCluster()
        self.use_mock = False
        self.k8s_client: Optional[Any] = None

        self._init_k8s_client()

    def _init_k8s_client(self):
        """Initializes connection to Kubernetes API or falls back to mock cluster."""
        if not K8S_AVAILABLE:
            self.use_mock = True
            return

        try:
            # First try in-cluster service account credentials
            config.load_incluster_config()
            self.k8s_client = client.CoreV1Api()
            logger.info("Connected to in-cluster Kubernetes API.")
        except Exception:
            try:
                # Then try local kubeconfig (~/.kube/config)
                config.load_kube_config()
                # Test connectivity with a fast timeout
                api_instance = client.CoreV1Api()
                api_instance.api_client.rest_client.pool_manager.connection_pool_kw['timeout'] = 2.0
                api_instance.list_namespaced_pod(namespace=self.namespace, limit=1)
                self.k8s_client = api_instance
                logger.info("Connected to local Kubernetes cluster via kubeconfig.")
            except Exception as e:
                if self.fallback_to_mock:
                    logger.info(f"Kubernetes cluster unreachable ({e}). Using MockKubernetesCluster fallback.")
                    self.use_mock = True
                else:
                    logger.error(f"Could not connect to Kubernetes cluster: {e}")
                    raise

    def warmup_tool_pod(
        self,
        tool_name: str,
        session_id: Optional[str] = None,
        ttl_seconds: float = 60.0
    ) -> PodProvisionResult:
        """
        Speculatively provisions or pre-warms a sandbox container for a given tool and session.
        """
        sid = session_id or str(uuid.uuid4())[:8]
        pod_name = f"streamops-{tool_name}-{sid}"

        # Load tool configuration
        registry = self._load_registry()
        tool_cfg = registry.get(tool_name, {
            "sandbox_image": "python:3.11-slim",
            "cpu_limit": "500m",
            "memory_limit": "512Mi"
        })

        image = tool_cfg.get("sandbox_image", "python:3.11-slim")
        cpu_limit = tool_cfg.get("cpu_limit", "500m")
        memory_limit = tool_cfg.get("memory_limit", "512Mi")

        if self.use_mock or not self.k8s_client:
            mock_pod = self.mock_cluster.create_pod(
                tool_name=tool_name,
                image=image,
                namespace=self.namespace,
                session_id=sid,
                ttl_seconds=ttl_seconds
            )
            return PodProvisionResult(
                success=True,
                pod_name=mock_pod.name,
                tool_name=tool_name,
                namespace=self.namespace,
                is_mock=True,
                status=mock_pod.current_status(),
                created_at=mock_pod.created_at
            )

        # Real Kubernetes Pod Creation
        try:
            # Check if pod already exists
            try:
                existing = self.k8s_client.read_namespaced_pod(name=pod_name, namespace=self.namespace)
                return PodProvisionResult(
                    success=True,
                    pod_name=pod_name,
                    tool_name=tool_name,
                    namespace=self.namespace,
                    is_mock=False,
                    status=existing.status.phase or "Running",
                    created_at=time.time()
                )
            except ApiException as e:
                if e.status != 404:
                    raise

            # Construct Pod manifest
            pod_manifest = client.V1Pod(
                api_version="v1",
                kind="Pod",
                metadata=client.V1ObjectMeta(
                    name=pod_name,
                    namespace=self.namespace,
                    labels={
                        "app": "streamops-sandbox",
                        "streamops-tool": tool_name,
                        "streamops-session": sid,
                        "streamops-state": "prewarmed",
                        "streamops-ttl": "active"
                    },
                    annotations={
                        "streamops.ai/created-at": str(time.time()),
                        "streamops.ai/ttl-seconds": str(ttl_seconds)
                    }
                ),
                spec=client.V1PodSpec(
                    restart_policy="Never",
                    containers=[
                        client.V1Container(
                            name=f"{tool_name}-sandbox",
                            image=image,
                            image_pull_policy="IfNotPresent",
                            command=["sleep", "3600"] if "python" in tool_name or "alpine" in image else None,
                            resources=client.V1ResourceRequirements(
                                limits={"cpu": cpu_limit, "memory": memory_limit},
                                requests={"cpu": "100m", "memory": "128Mi"}
                            )
                        )
                    ]
                )
            )

            created_pod = self.k8s_client.create_namespaced_pod(
                namespace=self.namespace,
                body=pod_manifest
            )
            logger.info(f"⚡ [K8S PROVISIONER] Created speculative pod '{pod_name}' in namespace '{self.namespace}'.")
            return PodProvisionResult(
                success=True,
                pod_name=pod_name,
                tool_name=tool_name,
                namespace=self.namespace,
                is_mock=False,
                status=created_pod.status.phase or "Pending",
                created_at=time.time()
            )

        except Exception as e:
            logger.warning(f"Error provisioning K8s pod ({e}). Falling back to mock pod.")
            mock_pod = self.mock_cluster.create_pod(
                tool_name=tool_name,
                image=image,
                namespace=self.namespace,
                session_id=sid,
                ttl_seconds=ttl_seconds
            )
            return PodProvisionResult(
                success=True,
                pod_name=mock_pod.name,
                tool_name=tool_name,
                namespace=self.namespace,
                is_mock=True,
                status=mock_pod.current_status(),
                created_at=mock_pod.created_at
            )

    def claim_pod(self, pod_name: str) -> bool:
        """Marks a pre-warmed pod as claimed by the agent tool execution."""
        if self.use_mock or not self.k8s_client:
            return self.mock_cluster.claim_pod(pod_name)

        try:
            patch_body = {
                "metadata": {
                    "labels": {
                        "streamops-state": "claimed",
                        "streamops-ttl": "claimed"
                    }
                }
            }
            self.k8s_client.patch_namespaced_pod(name=pod_name, namespace=self.namespace, body=patch_body)
            logger.info(f"Pod '{pod_name}' state transitioned to CLAIMED.")
            return True
        except Exception as e:
            logger.warning(f"Failed to claim pod {pod_name}: {e}")
            return False

    def cleanup_unused_pods(self, ttl_seconds: float = 60.0) -> int:
        """
        Garbage collects un-claimed speculative pods that have exceeded their TTL.
        """
        if self.use_mock or not self.k8s_client:
            return self.mock_cluster.garbage_collect(ttl_seconds)

        deleted_count = 0
        try:
            pods = self.k8s_client.list_namespaced_pod(
                namespace=self.namespace,
                label_selector="streamops-ttl=active"
            )

            now = time.time()
            for pod in pods.items:
                created_time = pod.metadata.creation_timestamp
                if created_time:
                    age = now - created_time.timestamp()
                    if age > ttl_seconds:
                        self.k8s_client.delete_namespaced_pod(
                            name=pod.metadata.name,
                            namespace=self.namespace
                        )
                        deleted_count += 1
                        logger.info(f"Reclaimed expired pod '{pod.metadata.name}' (Age: {age:.1f}s > {ttl_seconds}s).")
        except Exception as e:
            logger.warning(f"Error during K8s garbage collection: {e}")

        return deleted_count

    def _load_registry(self) -> Dict[str, Any]:
        if os.path.exists(self.registry_path):
            try:
                with open(self.registry_path, "r") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

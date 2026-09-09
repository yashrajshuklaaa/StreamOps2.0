import time
import uuid
import logging
from dataclasses import dataclass, field
from typing import Dict, Optional, List

logger = logging.getLogger("streamops.mock_k8s")

@dataclass
class MockPod:
    name: str
    namespace: str
    tool_name: str
    image: str
    status: str = "Pending"  # Pending -> ContainerCreating -> Running -> Terminated
    created_at: float = field(default_factory=time.time)
    claimed: bool = False
    ttl_seconds: float = 60.0

    def current_status(self) -> str:
        elapsed = time.time() - self.created_at
        if self.status == "Terminated":
            return "Terminated"
        if elapsed < 0.5:
            return "Pending"
        elif elapsed < 1.5:
            return "ContainerCreating"
        else:
            return "Running"

class MockKubernetesCluster:
    """
    In-memory mock Kubernetes cluster for offline testing and local dev.
    Accurately models pod creation latency, status lifecycle, and garbage collection.
    """

    def __init__(self):
        self.pods: Dict[str, MockPod] = {}

    def create_pod(
        self,
        tool_name: str,
        image: str,
        namespace: str = "default",
        session_id: Optional[str] = None,
        ttl_seconds: float = 60.0
    ) -> MockPod:
        sid = session_id or str(uuid.uuid4())[:8]
        pod_name = f"streamops-{tool_name}-{sid}"
        
        pod = MockPod(
            name=pod_name,
            namespace=namespace,
            tool_name=tool_name,
            image=image,
            created_at=time.time(),
            ttl_seconds=ttl_seconds
        )
        self.pods[pod_name] = pod
        logger.info(f"[MOCK K8S] Spawned Pod '{pod_name}' with image '{image}' in namespace '{namespace}'.")
        return pod

    def get_pod(self, pod_name: str) -> Optional[MockPod]:
        return self.pods.get(pod_name)

    def list_pods(self, namespace: str = "default") -> List[MockPod]:
        return [p for p in self.pods.values() if p.namespace == namespace and p.status != "Terminated"]

    def claim_pod(self, pod_name: str) -> bool:
        pod = self.pods.get(pod_name)
        if pod and pod.status != "Terminated":
            pod.claimed = True
            logger.info(f"[MOCK K8S] Pod '{pod_name}' claimed by agent session.")
            return True
        return False

    def delete_pod(self, pod_name: str) -> bool:
        if pod_name in self.pods:
            self.pods[pod_name].status = "Terminated"
            logger.info(f"[MOCK K8S] Pod '{pod_name}' deleted.")
            return True
        return False

    def garbage_collect(self, ttl_seconds: float = 60.0) -> int:
        now = time.time()
        deleted_count = 0
        for pod_name, pod in list(self.pods.items()):
            if not pod.claimed and pod.status != "Terminated":
                if (now - pod.created_at) > ttl_seconds:
                    pod.status = "Terminated"
                    deleted_count += 1
                    logger.info(f"[MOCK K8S GC] Reclaimed idle pod '{pod_name}' (Age: {now - pod.created_at:.1f}s > {ttl_seconds}s).")
        return deleted_count

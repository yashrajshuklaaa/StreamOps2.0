"""
Legacy Kubernetes Provisioner wrapper routing to streamops.k8s.controller.
"""

from streamops.k8s.controller import KubernetesSandboxController, PodProvisionResult
from streamops.k8s.mock_cluster import MockKubernetesCluster

_controller = KubernetesSandboxController()

def warmup_tool_pod(tool_name: str, namespace: str = "default") -> bool:
    res = _controller.warmup_tool_pod(tool_name=tool_name)
    return res.success

def cleanup_unused_pods(namespace: str = "default", ttl_seconds: float = 60.0) -> int:
    return _controller.cleanup_unused_pods(ttl_seconds=ttl_seconds)

if __name__ == "__main__":
    warmup_tool_pod("python")
    cleanup_unused_pods()

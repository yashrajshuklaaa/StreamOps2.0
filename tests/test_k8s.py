import pytest
from streamops.k8s.mock_cluster import MockKubernetesCluster
from streamops.k8s.controller import KubernetesSandboxController

def test_mock_k8s_lifecycle():
    cluster = MockKubernetesCluster()
    pod = cluster.create_pod(tool_name="python", image="python:3.11-slim", session_id="test1")
    assert pod.name == "streamops-python-test1"
    assert pod.tool_name == "python"
    assert not pod.claimed

    # Claim pod
    claimed = cluster.claim_pod(pod.name)
    assert claimed is True
    assert pod.claimed is True

    # Delete pod
    deleted = cluster.delete_pod(pod.name)
    assert deleted is True
    assert pod.status == "Terminated"

def test_k8s_controller_warmup_and_gc():
    controller = KubernetesSandboxController(fallback_to_mock=True)
    res = controller.warmup_tool_pod(tool_name="python", session_id="sess123")
    assert res.success is True
    assert "streamops-python-sess123" in res.pod_name

    claimed = controller.claim_pod(res.pod_name)
    assert claimed is True

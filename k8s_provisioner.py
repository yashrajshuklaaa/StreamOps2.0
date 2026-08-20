from kubernetes import client, config
from kubernetes.client.rest import ApiException
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_kube_config():
    try:
        config.load_kube_config()
        logger.info("Loaded local kube config.")
    except Exception as e:
        logger.warning(f"Failed to load local kube config: {e}. Trying in-cluster config.")
        try:
            config.load_incluster_config()
            logger.info("Loaded in-cluster kube config.")
        except Exception as e2:
            logger.error("Could not load any kube config.")

def warmup_tool_pod(tool_name: str, namespace="default"):
    """
    Spins up a lightweight tool pod if it doesn't already exist.
    """
    pod_configs = {
        "python": {"image": "python:3.9-slim", "name": "python-sandbox"},
        "sql": {"image": "postgres:13-alpine", "name": "sql-sandbox"},
        "browser": {"image": "selenium/standalone-chromium", "name": "browser-sandbox"}
    }
    
    if tool_name not in pod_configs:
        logger.error(f"Unknown tool intent: {tool_name}")
        return False
        
    pod_name = pod_configs[tool_name]["name"]
    image = pod_configs[tool_name]["image"]

    try:
        load_kube_config()
        v1 = client.CoreV1Api()
        
        # Check if pod already exists
        v1.read_namespaced_pod(name=pod_name, namespace=namespace)
        logger.info(f"Pod {pod_name} is already running or being created.")
        return True
    except ApiException as e:
        if e.status != 404:
            logger.error(f"Error checking pod: {e}")
            return False
    except Exception as e:
        logger.warning("Kubernetes cluster not reachable. Mocking Pod creation for demonstration.")
        import time
        time.sleep(1) # Simulate API call latency
        logger.info(f"[MOCK] Successfully initiated pod {pod_name} creation.")
        return True

    logger.info(f"Pod {pod_name} not found. Triggering Just-in-Time provisioning...")
    
    # Define pod
    pod = client.V1Pod(
        api_version="v1",
        kind="Pod",
        metadata=client.V1ObjectMeta(
            name=pod_name,
            labels={"streamops-ttl": "active"} # For garbage collection
        ),
        spec=client.V1PodSpec(
            containers=[
                client.V1Container(
                    name=f"{tool_name}-env",
                    image=image,
                    command=["sleep", "3600"] if tool_name == "python" else None, # Keep alive for a while
                    image_pull_policy="IfNotPresent"
                )
            ],
            restart_policy="Never"
        )
    )
    
    try:
        v1.create_namespaced_pod(namespace=namespace, body=pod)
        logger.info(f"Successfully initiated pod {pod_name} creation.")
        return True
    except ApiException as e:
        logger.error(f"Failed to create pod: {e}")
        return False

def cleanup_unused_pods(namespace="default", ttl_seconds=60):
    """
    Simulates a background process that cleans up pre-warmed pods 
    if they haven't been 'claimed' by an agent within TTL.
    """
    try:
        load_kube_config()
        v1 = client.CoreV1Api()
        
        # Get all pods with our specific label
        pods = v1.list_namespaced_pod(
            namespace=namespace,
            label_selector="streamops-ttl=active"
        )
        
        import time
        for pod in pods.items:
            # Check the pod's creation timestamp
            creation_time = pod.metadata.creation_timestamp
            if creation_time:
                # Convert to current time and check age
                age = time.time() - creation_time.timestamp()
                if age > ttl_seconds:
                    logger.info(f"Pod {pod.metadata.name} expired (TTL {ttl_seconds}s). Deleting...")
                    v1.delete_namespaced_pod(name=pod.metadata.name, namespace=namespace)
    except Exception as e:
        logger.warning(f"Garbage collection skipped (cluster unreachable or error): {e}")

if __name__ == "__main__":
    warmup_tool_pod("python")
    cleanup_unused_pods()

"""
Stream-Ops Semantic Proxy (Legacy Wrapper / Entrypoint)
Redirects to the modular streamops.proxy.server implementation.
"""

from streamops.proxy.server import app, trigger_k8s_provisioning

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

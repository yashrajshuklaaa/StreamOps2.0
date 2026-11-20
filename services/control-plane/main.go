package main

import (
	"context"
	"errors"
	"fmt"
	"log"
	"net/http"
	"os"
	"strconv"
	"strings"
	"time"

	"k8s.io/client-go/kubernetes"
	"k8s.io/client-go/rest"
	"k8s.io/client-go/tools/clientcmd"
)

type config struct {
	listenAddr       string
	namespace        string
	ollamaURL        string
	intentURL        string
	prefetchTTL      time.Duration
	prefetchInterval time.Duration
}

func loadConfig() (config, error) {
	cfg := config{
		listenAddr:       envOr("STREAMOPS_LISTEN_ADDR", ":8000"),
		namespace:        envOr("STREAMOPS_NAMESPACE", "streamops"),
		ollamaURL:        envOr("OLLAMA_URL", "http://127.0.0.1:11434/api/generate"),
		intentURL:        strings.TrimRight(envOr("INTENT_ENGINE_URL", "http://127.0.0.1:8081"), "/"),
		prefetchInterval: 10 * time.Second,
	}
	ttlSeconds, err := strconv.Atoi(envOr("PREFETCH_TTL_SECONDS", "60"))
	if err != nil || ttlSeconds < 10 {
		return config{}, errors.New("PREFETCH_TTL_SECONDS must be an integer of at least 10")
	}
	cfg.prefetchTTL = time.Duration(ttlSeconds) * time.Second
	if cfg.namespace == "" {
		return config{}, errors.New("STREAMOPS_NAMESPACE must not be empty")
	}
	return cfg, nil
}

func newKubernetesClient(ctx context.Context) (kubernetes.Interface, error) {
	clusterConfig, err := rest.InClusterConfig()
	if err != nil {
		loadingRules := clientcmd.NewDefaultClientConfigLoadingRules()
		if kubeconfig := os.Getenv("KUBECONFIG"); kubeconfig != "" {
			loadingRules.ExplicitPath = kubeconfig
		}
		clusterConfig, err = clientcmd.NewNonInteractiveDeferredLoadingClientConfig(
			loadingRules,
			&clientcmd.ConfigOverrides{},
		).ClientConfig()
		if err != nil {
			return nil, fmt.Errorf("load Kubernetes credentials (in-cluster or kubeconfig): %w", err)
		}
	}

	client, err := kubernetes.NewForConfig(clusterConfig)
	if err != nil {
		return nil, fmt.Errorf("create Kubernetes client: %w", err)
	}
	return client, nil
}

func main() {
	cfg, err := loadConfig()
	if err != nil {
		log.Fatal(err)
	}
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	kube, err := newKubernetesClient(ctx)
	cancel()
	if err != nil {
		log.Fatalf("Kubernetes is required; refusing to start in mock mode: %v", err)
	}

	cp := newControlPlane(cfg, kube)
	go cp.runGarbageCollector(context.Background())
	server := &http.Server{
		Addr:              cfg.listenAddr,
		Handler:           cp.routes(),
		ReadHeaderTimeout: 5 * time.Second,
	}
	log.Printf("StreamOps Go control plane listening on %s (namespace=%s, ollama=%s, intent=%s)",
		cfg.listenAddr, cfg.namespace, cfg.ollamaURL, cfg.intentURL)
	log.Fatal(server.ListenAndServe())
}

func envOr(key, fallback string) string {
	if value := strings.TrimSpace(os.Getenv(key)); value != "" {
		return value
	}
	return fallback
}

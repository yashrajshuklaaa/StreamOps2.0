package main

import (
	"bufio"
	"bytes"
	"context"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log"
	"math"
	"net/http"
	"strings"
	"sync"
	"time"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promhttp"
	corev1 "k8s.io/api/core/v1"
	apierrors "k8s.io/apimachinery/pkg/api/errors"
	"k8s.io/apimachinery/pkg/api/resource"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/types"
	"k8s.io/client-go/kubernetes"
)

const (
	labelManaged = "streamops.ai/managed"
	labelTool    = "streamops.ai/tool"
	labelSession = "streamops.ai/session"
	labelState   = "streamops.ai/state"

	annotationTriggeredAt = "streamops.ai/triggered-at"
	annotationReadyAt     = "streamops.ai/ready-at"
	statePrewarmed        = "prewarmed"
	stateClaimed          = "claimed"
)

var (
	intentTriggers = prometheus.NewCounterVec(prometheus.CounterOpts{
		Name: "streamops_intent_triggers_total",
		Help: "Intent predictions that passed the cost-aware threshold.",
	}, []string{"tool", "stage"})
	podCreateErrors = prometheus.NewCounterVec(prometheus.CounterOpts{
		Name: "streamops_pod_create_errors_total",
		Help: "Kubernetes pod creation failures.",
	}, []string{"tool"})
	podReadySeconds = prometheus.NewHistogramVec(prometheus.HistogramOpts{
		Name:    "streamops_pod_trigger_to_ready_seconds",
		Help:    "Seconds from speculative trigger until the sandbox pod is ready.",
		Buckets: prometheus.DefBuckets,
	}, []string{"tool"})
	maskedSeconds = prometheus.NewCounterVec(prometheus.CounterOpts{
		Name: "streamops_cold_start_seconds_masked_total",
		Help: "Observed sandbox startup seconds overlapped by model reasoning before claim.",
	}, []string{"tool"})
	reclaimedPods = prometheus.NewCounterVec(prometheus.CounterOpts{
		Name: "streamops_speculative_pods_reclaimed_total",
		Help: "Unclaimed speculative pods deleted after their TTL.",
	}, []string{"tool"})
)

func init() {
	prometheus.MustRegister(intentTriggers, podCreateErrors, podReadySeconds, maskedSeconds, reclaimedPods)
}

type ControlPlane struct {
	cfg        config
	kube       kubernetes.Interface
	httpClient *http.Client
	readyMu    sync.Mutex
	readyPods  map[string]struct{}
}

type intentRequest struct {
	SessionID   string `json:"session_id"`
	Text        string `json:"text"`
	IsReasoning bool   `json:"is_reasoning"`
}

type intentDecision struct {
	ShouldTrigger   bool     `json:"should_trigger"`
	ToolName        string   `json:"tool_name"`
	Confidence      float64  `json:"confidence"`
	Threshold       float64  `json:"threshold"`
	DetectionStage  string   `json:"detection_stage"`
	MatchedKeywords []string `json:"matched_keywords"`
}

type ollamaChunk struct {
	Response string `json:"response"`
	Done     bool   `json:"done"`
}

type claimRequest struct {
	ToolName string `json:"tool_name"`
}

type claimResponse struct {
	PodName          string  `json:"pod_name"`
	Namespace        string  `json:"namespace"`
	Phase            string  `json:"phase"`
	Ready            bool    `json:"ready"`
	MaskedSeconds    float64 `json:"masked_seconds"`
	ReadyWaitSeconds float64 `json:"ready_wait_seconds"`
}

type toolSpec struct {
	image   string
	cpu     string
	memory  string
	command []string
}

var toolSpecs = map[string]toolSpec{
	"python": {
		image:   "python:3.11-slim",
		cpu:     "500m",
		memory:  "512Mi",
		command: []string{"python", "-c", "import time; time.sleep(3600)"},
	},
	"bash": {
		image:   "alpine:3.20",
		cpu:     "250m",
		memory:  "256Mi",
		command: []string{"sh", "-c", "sleep 3600"},
	},
	"sql": {
		image:  "postgres:15-alpine",
		cpu:    "500m",
		memory: "512Mi",
	},
	"browser": {
		image:  "selenium/standalone-chrome:latest",
		cpu:    "1000m",
		memory: "2Gi",
	},
}

func newControlPlane(cfg config, kube kubernetes.Interface) *ControlPlane {
	return &ControlPlane{
		cfg:  cfg,
		kube: kube,
		httpClient: &http.Client{
			Transport: &http.Transport{
				MaxIdleConns:        100,
				MaxIdleConnsPerHost: 20,
				IdleConnTimeout:     90 * time.Second,
			},
		},
		readyPods: make(map[string]struct{}),
	}
}

func (cp *ControlPlane) routes() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /healthz", cp.health)
	mux.HandleFunc("GET /readyz", cp.ready)
	mux.Handle("GET /metrics", promhttp.Handler())
	mux.HandleFunc("POST /api/generate", cp.generate)
	mux.HandleFunc("POST /v1/sessions/{session_id}/claim", cp.claim)
	return mux
}

func (cp *ControlPlane) health(w http.ResponseWriter, _ *http.Request) {
	writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
}

func (cp *ControlPlane) ready(w http.ResponseWriter, r *http.Request) {
	ctx, cancel := context.WithTimeout(r.Context(), 2*time.Second)
	defer cancel()
	if _, err := cp.kube.CoreV1().Pods(cp.cfg.namespace).List(ctx, metav1.ListOptions{Limit: 1}); err != nil {
		http.Error(w, "Kubernetes API is not ready: "+err.Error(), http.StatusServiceUnavailable)
		return
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, cp.cfg.intentURL+"/healthz", nil)
	if err != nil {
		http.Error(w, "create intent health request: "+err.Error(), http.StatusServiceUnavailable)
		return
	}
	resp, err := cp.httpClient.Do(req)
	if err != nil {
		http.Error(w, "intent engine is unavailable: "+err.Error(), http.StatusServiceUnavailable)
		return
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		http.Error(w, fmt.Sprintf("intent engine returned %s", resp.Status), http.StatusServiceUnavailable)
		return
	}
	writeJSON(w, http.StatusOK, map[string]string{"status": "ready", "namespace": cp.cfg.namespace})
}

func (cp *ControlPlane) generate(w http.ResponseWriter, r *http.Request) {
	r.Body = http.MaxBytesReader(w, r.Body, 2<<20)
	body, err := io.ReadAll(r.Body)
	if err != nil {
		http.Error(w, "read request body: "+err.Error(), http.StatusBadRequest)
		return
	}
	var input map[string]json.RawMessage
	if err := json.Unmarshal(body, &input); err != nil {
		http.Error(w, "request body must be valid JSON: "+err.Error(), http.StatusBadRequest)
		return
	}
	sessionID, err := newSessionID()
	if err != nil {
		http.Error(w, "create session ID: "+err.Error(), http.StatusInternalServerError)
		return
	}

	upstreamRequest, err := http.NewRequestWithContext(r.Context(), http.MethodPost, cp.cfg.ollamaURL, bytes.NewReader(body))
	if err != nil {
		http.Error(w, "create Ollama request: "+err.Error(), http.StatusInternalServerError)
		return
	}
	upstreamRequest.Header.Set("Content-Type", "application/json")
	upstreamResponse, err := cp.httpClient.Do(upstreamRequest)
	if err != nil {
		http.Error(w, "Ollama backend request failed: "+err.Error(), http.StatusBadGateway)
		return
	}
	defer upstreamResponse.Body.Close()

	w.Header().Set("Content-Type", upstreamResponse.Header.Get("Content-Type"))
	w.Header().Set("X-StreamOps-Session-ID", sessionID)
	w.WriteHeader(upstreamResponse.StatusCode)
	if upstreamResponse.StatusCode < 200 || upstreamResponse.StatusCode >= 300 {
		if _, err := io.Copy(w, upstreamResponse.Body); err != nil {
			log.Printf("session=%s copy Ollama error response: %v", sessionID, err)
		}
		return
	}

	reader := bufio.NewReader(upstreamResponse.Body)
	for {
		line, readErr := reader.ReadBytes('\n')
		if len(line) > 0 {
			var chunk ollamaChunk
			if err := json.Unmarshal(bytes.TrimSpace(line), &chunk); err == nil && chunk.Response != "" {
				cp.inspectChunk(r.Context(), sessionID, chunk.Response)
			}
			if _, err := w.Write(line); err != nil {
				log.Printf("session=%s write streamed response: %v", sessionID, err)
				return
			}
			if flusher, ok := w.(http.Flusher); ok {
				flusher.Flush()
			}
		}
		if readErr != nil {
			if !errors.Is(readErr, io.EOF) {
				log.Printf("session=%s read Ollama stream: %v", sessionID, readErr)
			}
			return
		}
	}
}

func (cp *ControlPlane) inspectChunk(ctx context.Context, sessionID, text string) {
	body, err := json.Marshal(intentRequest{SessionID: sessionID, Text: text})
	if err != nil {
		log.Printf("session=%s encode intent request: %v", sessionID, err)
		return
	}
	callCtx, cancel := context.WithTimeout(ctx, 500*time.Millisecond)
	defer cancel()
	req, err := http.NewRequestWithContext(callCtx, http.MethodPost, cp.cfg.intentURL+"/v1/chunks", bytes.NewReader(body))
	if err != nil {
		log.Printf("session=%s create intent request: %v", sessionID, err)
		return
	}
	req.Header.Set("Content-Type", "application/json")
	resp, err := cp.httpClient.Do(req)
	if err != nil {
		log.Printf("session=%s intent engine request failed: %v", sessionID, err)
		return
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		responseBody, _ := io.ReadAll(io.LimitReader(resp.Body, 4096))
		log.Printf("session=%s intent engine returned %s: %s", sessionID, resp.Status, strings.TrimSpace(string(responseBody)))
		return
	}
	var decision intentDecision
	if err := json.NewDecoder(io.LimitReader(resp.Body, 16<<10)).Decode(&decision); err != nil {
		log.Printf("session=%s decode intent decision: %v", sessionID, err)
		return
	}
	if !decision.ShouldTrigger {
		return
	}
	if _, ok := toolSpecs[decision.ToolName]; !ok {
		log.Printf("session=%s intent engine returned unsupported tool %q", sessionID, decision.ToolName)
		return
	}
	intentTriggers.WithLabelValues(decision.ToolName, decision.DetectionStage).Inc()
	log.Printf("session=%s speculative intent tool=%s confidence=%.3f threshold=%.3f stage=%s",
		sessionID, decision.ToolName, decision.Confidence, decision.Threshold, decision.DetectionStage)
	go cp.prewarm(sessionID, decision.ToolName)
}

func (cp *ControlPlane) prewarm(sessionID, toolName string) {
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	spec := toolSpecs[toolName]
	now := time.Now().UTC()
	pod := &corev1.Pod{
		ObjectMeta: metav1.ObjectMeta{
			Name:      podName(toolName, sessionID),
			Namespace: cp.cfg.namespace,
			Labels: map[string]string{
				labelManaged: "true",
				labelTool:    toolName,
				labelSession: sessionID,
				labelState:   statePrewarmed,
			},
			Annotations: map[string]string{
				annotationTriggeredAt: now.Format(time.RFC3339Nano),
			},
		},
		Spec: corev1.PodSpec{
			RestartPolicy:                 corev1.RestartPolicyNever,
			AutomountServiceAccountToken:  boolPtr(false),
			TerminationGracePeriodSeconds: int64Ptr(5),
			Containers: []corev1.Container{{
				Name:            "sandbox",
				Image:           spec.image,
				ImagePullPolicy: corev1.PullIfNotPresent,
				Command:         spec.command,
				Resources: corev1.ResourceRequirements{
					Requests: corev1.ResourceList{
						corev1.ResourceCPU:    resource.MustParse("100m"),
						corev1.ResourceMemory: resource.MustParse("64Mi"),
					},
					Limits: corev1.ResourceList{
						corev1.ResourceCPU:    resource.MustParse(spec.cpu),
						corev1.ResourceMemory: resource.MustParse(spec.memory),
					},
				},
				SecurityContext: sandboxSecurityContext(toolName),
			}},
		},
	}
	if toolName == "sql" {
		pod.Spec.Containers[0].Env = []corev1.EnvVar{{
			Name: "POSTGRES_PASSWORD", Value: randomPassword(),
		}}
	}

	created, err := cp.kube.CoreV1().Pods(cp.cfg.namespace).Create(ctx, pod, metav1.CreateOptions{})
	if apierrors.IsAlreadyExists(err) {
		created, err = cp.kube.CoreV1().Pods(cp.cfg.namespace).Get(ctx, pod.Name, metav1.GetOptions{})
	}
	if err != nil {
		podCreateErrors.WithLabelValues(toolName).Inc()
		log.Printf("session=%s create speculative pod %s: %v", sessionID, pod.Name, err)
		return
	}
	log.Printf("session=%s created speculative pod=%s phase=%s image=%s",
		sessionID, created.Name, created.Status.Phase, spec.image)
	cp.observeReady(created.Name, toolName)
}

func (cp *ControlPlane) observeReady(name, toolName string) {
	cp.readyMu.Lock()
	if _, exists := cp.readyPods[name]; exists {
		cp.readyMu.Unlock()
		return
	}
	cp.readyPods[name] = struct{}{}
	cp.readyMu.Unlock()

	go func() {
		defer func() {
			cp.readyMu.Lock()
			delete(cp.readyPods, name)
			cp.readyMu.Unlock()
		}()
		deadline := time.NewTimer(5 * time.Minute)
		defer deadline.Stop()
		ticker := time.NewTicker(500 * time.Millisecond)
		defer ticker.Stop()
		for {
			ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
			pod, err := cp.kube.CoreV1().Pods(cp.cfg.namespace).Get(ctx, name, metav1.GetOptions{})
			cancel()
			if err != nil {
				if !apierrors.IsNotFound(err) {
					log.Printf("observe pod=%s readiness: %v", name, err)
				}
				return
			}
			if readyAt := podReadyTime(pod); !readyAt.IsZero() {
				if pod.Annotations[annotationReadyAt] == "" {
					patch, _ := json.Marshal(map[string]any{"metadata": map[string]any{
						"annotations": map[string]string{annotationReadyAt: readyAt.UTC().Format(time.RFC3339Nano)},
					}})
					ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
					_, err := cp.kube.CoreV1().Pods(cp.cfg.namespace).Patch(ctx, name, types.MergePatchType, patch, metav1.PatchOptions{})
					cancel()
					if err != nil {
						log.Printf("record pod=%s ready timestamp: %v", name, err)
					}
				}
				if triggeredAt, err := time.Parse(time.RFC3339Nano, pod.Annotations[annotationTriggeredAt]); err == nil {
					seconds := readyAt.Sub(triggeredAt).Seconds()
					if seconds >= 0 {
						podReadySeconds.WithLabelValues(toolName).Observe(seconds)
					}
				}
				log.Printf("pod=%s is Ready", name)
				return
			}
			select {
			case <-deadline.C:
				log.Printf("pod=%s did not become Ready within five minutes", name)
				return
			case <-ticker.C:
			}
		}
	}()
}

func (cp *ControlPlane) claim(w http.ResponseWriter, r *http.Request) {
	sessionID := r.PathValue("session_id")
	if !validSessionID(sessionID) {
		http.Error(w, "invalid session ID", http.StatusBadRequest)
		return
	}
	var input claimRequest
	if err := json.NewDecoder(http.MaxBytesReader(w, r.Body, 8<<10)).Decode(&input); err != nil {
		http.Error(w, "request body must contain a valid tool_name: "+err.Error(), http.StatusBadRequest)
		return
	}
	if _, ok := toolSpecs[input.ToolName]; !ok {
		http.Error(w, "unsupported tool_name", http.StatusBadRequest)
		return
	}
	name := podName(input.ToolName, sessionID)
	ctx, cancel := context.WithTimeout(r.Context(), 5*time.Minute)
	defer cancel()
	pods := cp.kube.CoreV1().Pods(cp.cfg.namespace)
	pod, err := pods.Get(ctx, name, metav1.GetOptions{})
	if apierrors.IsNotFound(err) {
		http.Error(w, "speculative pod not found", http.StatusNotFound)
		return
	}
	if err != nil {
		http.Error(w, "read speculative pod: "+err.Error(), http.StatusInternalServerError)
		return
	}
	if pod.Labels[labelManaged] != "true" || pod.Labels[labelSession] != sessionID || pod.Labels[labelTool] != input.ToolName {
		http.Error(w, "pod metadata does not match this session", http.StatusConflict)
		return
	}

	claimAt := time.Now().UTC()
	patch, err := json.Marshal(map[string]any{"metadata": map[string]any{
		"labels": map[string]string{labelState: stateClaimed},
	}})
	if err != nil {
		http.Error(w, "encode claim update: "+err.Error(), http.StatusInternalServerError)
		return
	}
	pod, err = pods.Patch(ctx, name, types.MergePatchType, patch, metav1.PatchOptions{})
	if err != nil {
		http.Error(w, "claim speculative pod: "+err.Error(), http.StatusInternalServerError)
		return
	}
	readyAt, waitSeconds, err := cp.waitUntilReady(ctx, name, pod)
	if err != nil {
		http.Error(w, "wait for claimed pod: "+err.Error(), http.StatusGatewayTimeout)
		return
	}
	triggeredAt, err := time.Parse(time.RFC3339Nano, pod.Annotations[annotationTriggeredAt])
	if err != nil {
		http.Error(w, "pod has no valid trigger timestamp", http.StatusInternalServerError)
		return
	}
	masked := math.Max(0, math.Min(readyAt.Sub(triggeredAt).Seconds(), claimAt.Sub(triggeredAt).Seconds()))
	maskedSeconds.WithLabelValues(input.ToolName).Add(masked)
	writeJSON(w, http.StatusOK, claimResponse{
		PodName: name, Namespace: cp.cfg.namespace, Phase: string(pod.Status.Phase),
		Ready: true, MaskedSeconds: masked, ReadyWaitSeconds: waitSeconds,
	})
}

func (cp *ControlPlane) waitUntilReady(ctx context.Context, name string, pod *corev1.Pod) (time.Time, float64, error) {
	started := time.Now()
	if readyAt := podReadyTime(pod); !readyAt.IsZero() {
		return readyAt, 0, nil
	}
	ticker := time.NewTicker(500 * time.Millisecond)
	defer ticker.Stop()
	for {
		select {
		case <-ctx.Done():
			return time.Time{}, time.Since(started).Seconds(), ctx.Err()
		case <-ticker.C:
			latest, err := cp.kube.CoreV1().Pods(cp.cfg.namespace).Get(ctx, name, metav1.GetOptions{})
			if err != nil {
				return time.Time{}, time.Since(started).Seconds(), err
			}
			if latest.Status.Phase == corev1.PodFailed {
				return time.Time{}, time.Since(started).Seconds(), fmt.Errorf("pod failed: %s", latest.Status.Reason)
			}
			if readyAt := podReadyTime(latest); !readyAt.IsZero() {
				return readyAt, time.Since(started).Seconds(), nil
			}
		}
	}
}

func (cp *ControlPlane) runGarbageCollector(ctx context.Context) {
	ticker := time.NewTicker(cp.cfg.prefetchInterval)
	defer ticker.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			cp.reclaimExpired(ctx)
		}
	}
}

func (cp *ControlPlane) reclaimExpired(parent context.Context) {
	ctx, cancel := context.WithTimeout(parent, 10*time.Second)
	defer cancel()
	list, err := cp.kube.CoreV1().Pods(cp.cfg.namespace).List(ctx, metav1.ListOptions{
		LabelSelector: labelManaged + "=true," + labelState + "=" + statePrewarmed,
	})
	if err != nil {
		log.Printf("list speculative pods for TTL cleanup: %v", err)
		return
	}
	now := time.Now()
	for _, pod := range list.Items {
		triggeredAt, err := time.Parse(time.RFC3339Nano, pod.Annotations[annotationTriggeredAt])
		if err != nil {
			log.Printf("skip pod=%s with invalid trigger timestamp: %v", pod.Name, err)
			continue
		}
		if now.Sub(triggeredAt) < cp.cfg.prefetchTTL {
			continue
		}
		if err := cp.kube.CoreV1().Pods(cp.cfg.namespace).Delete(ctx, pod.Name, metav1.DeleteOptions{}); err != nil {
			if !apierrors.IsNotFound(err) {
				log.Printf("delete expired speculative pod=%s: %v", pod.Name, err)
			}
			continue
		}
		reclaimedPods.WithLabelValues(pod.Labels[labelTool]).Inc()
		log.Printf("reclaimed unclaimed speculative pod=%s age=%s", pod.Name, now.Sub(triggeredAt).Round(time.Second))
	}
}

func (cp *ControlPlane) callIntentHealth(ctx context.Context) error {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, cp.cfg.intentURL+"/healthz", nil)
	if err != nil {
		return err
	}
	resp, err := cp.httpClient.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("intent engine returned %s", resp.Status)
	}
	return nil
}

func newSessionID() (string, error) {
	var raw [16]byte
	if _, err := rand.Read(raw[:]); err != nil {
		return "", err
	}
	return hex.EncodeToString(raw[:]), nil
}

func podName(toolName, sessionID string) string {
	return "streamops-" + toolName + "-" + sessionID
}

func validSessionID(sessionID string) bool {
	if len(sessionID) != 32 {
		return false
	}
	_, err := hex.DecodeString(sessionID)
	return err == nil
}

func podReadyTime(pod *corev1.Pod) time.Time {
	for _, condition := range pod.Status.Conditions {
		if condition.Type == corev1.PodReady && condition.Status == corev1.ConditionTrue {
			return condition.LastTransitionTime.Time
		}
	}
	return time.Time{}
}

func sandboxSecurityContext(toolName string) *corev1.SecurityContext {
	context := &corev1.SecurityContext{
		AllowPrivilegeEscalation: boolPtr(false),
		Capabilities:             &corev1.Capabilities{Drop: []corev1.Capability{"ALL"}},
		SeccompProfile:           &corev1.SeccompProfile{Type: corev1.SeccompProfileTypeRuntimeDefault},
	}
	if toolName == "python" || toolName == "bash" {
		context.RunAsNonRoot = boolPtr(true)
		context.RunAsUser = int64Ptr(10001)
	}
	return context
}

func randomPassword() string {
	var raw [24]byte
	if _, err := rand.Read(raw[:]); err != nil {
		log.Printf("generate ephemeral database password: %v", err)
		return ""
	}
	return hex.EncodeToString(raw[:])
}

func boolPtr(value bool) *bool { return &value }

func int64Ptr(value int64) *int64 { return &value }

func writeJSON(w http.ResponseWriter, status int, value any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	if err := json.NewEncoder(w).Encode(value); err != nil {
		log.Printf("write JSON response: %v", err)
	}
}

package main

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	corev1 "k8s.io/api/core/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/client-go/kubernetes/fake"
)

func testConfig() config {
	return config{
		listenAddr:       ":0",
		namespace:        "streamops",
		ollamaURL:        "http://ollama.invalid/api/generate",
		intentURL:        "http://intent.invalid",
		prefetchTTL:      time.Minute,
		prefetchInterval: time.Second,
	}
}

func TestPrewarmCreatesRestrictedPodWithResourceBounds(t *testing.T) {
	kube := fake.NewSimpleClientset(&corev1.Namespace{ObjectMeta: metav1.ObjectMeta{Name: "streamops"}})
	cp := newControlPlane(testConfig(), kube)
	sessionID := "0123456789abcdef0123456789abcdef"

	cp.prewarm(sessionID, "python")

	pod, err := kube.CoreV1().Pods("streamops").Get(t.Context(), podName("python", sessionID), metav1.GetOptions{})
	if err != nil {
		t.Fatalf("get prewarmed pod: %v", err)
	}
	if pod.Labels[labelState] != statePrewarmed || pod.Labels[labelSession] != sessionID {
		t.Fatalf("unexpected pod labels: %#v", pod.Labels)
	}
	container := pod.Spec.Containers[0]
	if container.Image != "python:3.11-slim" {
		t.Fatalf("unexpected sandbox image: %s", container.Image)
	}
	if container.Resources.Limits.Cpu().String() != "500m" || container.Resources.Limits.Memory().String() != "512Mi" {
		t.Fatalf("pod has unexpected resource limits: %#v", container.Resources.Limits)
	}
	if pod.Spec.AutomountServiceAccountToken == nil || *pod.Spec.AutomountServiceAccountToken {
		t.Fatal("sandbox pod must not receive a service-account token")
	}
	if container.SecurityContext == nil || container.SecurityContext.AllowPrivilegeEscalation == nil || *container.SecurityContext.AllowPrivilegeEscalation {
		t.Fatal("sandbox must disallow privilege escalation")
	}
}

func TestClaimMarksReadyPodAndReportsMeasuredOverlap(t *testing.T) {
	sessionID := "0123456789abcdef0123456789abcdef"
	triggeredAt := time.Now().Add(-3 * time.Second)
	readyAt := triggeredAt.Add(1500 * time.Millisecond)
	pod := &corev1.Pod{
		ObjectMeta: metav1.ObjectMeta{
			Name:      podName("python", sessionID),
			Namespace: "streamops",
			Labels: map[string]string{
				labelManaged: "true",
				labelTool:    "python",
				labelSession: sessionID,
				labelState:   statePrewarmed,
			},
			Annotations: map[string]string{
				annotationTriggeredAt: triggeredAt.Format(time.RFC3339Nano),
			},
		},
		Status: corev1.PodStatus{
			Phase: corev1.PodRunning,
			Conditions: []corev1.PodCondition{{
				Type: corev1.PodReady, Status: corev1.ConditionTrue, LastTransitionTime: metav1.NewTime(readyAt),
			}},
		},
	}
	kube := fake.NewSimpleClientset(&corev1.Namespace{ObjectMeta: metav1.ObjectMeta{Name: "streamops"}}, pod)
	cp := newControlPlane(testConfig(), kube)
	request := httptest.NewRequest(http.MethodPost, "/v1/sessions/"+sessionID+"/claim", strings.NewReader(`{"tool_name":"python"}`))
	response := httptest.NewRecorder()

	cp.routes().ServeHTTP(response, request)

	if response.Code != http.StatusOK {
		t.Fatalf("claim returned %d: %s", response.Code, response.Body.String())
	}
	var result claimResponse
	if err := json.Unmarshal(response.Body.Bytes(), &result); err != nil {
		t.Fatalf("decode claim response: %v", err)
	}
	if !result.Ready || result.MaskedSeconds < 0 {
		t.Fatalf("unexpected measured overlap: %#v", result)
	}
	claimed, err := kube.CoreV1().Pods("streamops").Get(t.Context(), pod.Name, metav1.GetOptions{})
	if err != nil {
		t.Fatalf("get claimed pod: %v", err)
	}
	if claimed.Labels[labelState] != stateClaimed {
		t.Fatalf("pod state was not claimed: %s", claimed.Labels[labelState])
	}
}

func TestGarbageCollectorDeletesOnlyExpiredUnclaimedPods(t *testing.T) {
	expiredAt := time.Now().Add(-2 * time.Minute)
	expired := &corev1.Pod{
		ObjectMeta: metav1.ObjectMeta{
			Name:      "expired",
			Namespace: "streamops",
			Labels:    map[string]string{labelManaged: "true", labelState: statePrewarmed, labelTool: "python"},
			Annotations: map[string]string{
				annotationTriggeredAt: expiredAt.Format(time.RFC3339Nano),
			},
		},
	}
	claimed := expired.DeepCopy()
	claimed.Name = "claimed"
	claimed.Labels[labelState] = stateClaimed
	kube := fake.NewSimpleClientset(
		&corev1.Namespace{ObjectMeta: metav1.ObjectMeta{Name: "streamops"}},
		expired,
		claimed,
	)
	cp := newControlPlane(testConfig(), kube)

	cp.reclaimExpired(t.Context())

	if _, err := kube.CoreV1().Pods("streamops").Get(t.Context(), "expired", metav1.GetOptions{}); err == nil {
		t.Fatal("expected expired speculative pod to be deleted")
	}
	if _, err := kube.CoreV1().Pods("streamops").Get(t.Context(), "claimed", metav1.GetOptions{}); err != nil {
		t.Fatalf("claimed pod must be retained: %v", err)
	}
}

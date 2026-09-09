document.addEventListener("DOMContentLoaded", () => {
    // DOM Elements
    const promptInput = document.getElementById("prompt-input");
    const modelInput = document.getElementById("model-input");
    const presetSelector = document.getElementById("prompt-presets");
    const btnRunStream = document.getElementById("btn-run-stream");
    const tokenStreamBox = document.getElementById("token-stream-box");
    const streamStatus = document.getElementById("stream-status");
    const confidenceBar = document.getElementById("confidence-bar");
    const confidencePercentage = document.getElementById("confidence-percentage");
    const detectedToolName = document.getElementById("detected-tool-name");
    const finopsDecision = document.getElementById("finops-decision");
    const intentStageBadge = document.getElementById("intent-stage-badge");
    const thresholdMarker = document.getElementById("threshold-marker");
    const podListContainer = document.getElementById("pod-list-container");
    const activePodCount = document.getElementById("active-pod-count");
    const totalLatencyMasked = document.getElementById("total-latency-masked");

    // Scenarios
    const PRESETS = {
        python: {
            prompt: "I have a dataset of 1,000 users in CSV format. I need to calculate average retention, group by country, and plot a distribution chart. First think through the steps, then write the Python pandas code.",
            model: "llama3:8b",
            tool: "python",
            threshold: 35,
            coldStart: 5.5,
            description: "Speculative Python sandbox pre-warmed during CoT"
        },
        deepseek: {
            prompt: "<think>The user wants to optimize a quadratic loss function. Let me formulate the gradient descent update equation. I will need to write a python script to simulate convergence and plot iterations.</think>Here is the mathematical formulation and python implementation.",
            model: "deepseek-r1",
            tool: "python",
            threshold: 35,
            coldStart: 5.5,
            description: "DeepSeek <think> token intercepted for early lookahead"
        },
        ml_training: {
            prompt: "The user wants to fine-tune a BERT model on a custom NLP dataset. I will set up a PyTorch training loop with a DataLoader, configure the Adam optimizer, define cross-entropy loss, and run 10 epochs on GPU. Let me write the full training script.",
            model: "llama3:8b",
            tool: "python",
            threshold: 38,
            coldStart: 7.2,
            description: "GPU-enabled PyTorch training container pre-warmed"
        },
        sql: {
            prompt: "We need to identify all active subscriptions expiring in the next 30 days. Let me analyze the relational database schema, join user_accounts with billing_subscriptions, and construct the Postgres SQL query.",
            model: "llama3:8b",
            tool: "sql",
            threshold: 40,
            coldStart: 6.2,
            description: "Postgres SQL execution sandbox pre-warmed"
        },
        redis: {
            prompt: "Our API response times are spiking. I suspect the cache-aside pattern is broken. Let me connect to Redis, inspect the TTL on the session keys, flush stale entries with SCAN+DEL, and benchmark throughput with redis-py.",
            model: "llama3:8b",
            tool: "redis",
            threshold: 42,
            coldStart: 4.8,
            description: "Redis client container pre-warmed for cache ops"
        },
        file_processing: {
            prompt: "The user uploaded a quarterly revenue report as a PDF. I need to extract tabular data using pdfplumber, convert it to an Excel workbook with openpyxl, and produce a pivot table summary. Let me write the file processing pipeline.",
            model: "llama3:8b",
            tool: "python",
            threshold: 36,
            coldStart: 5.5,
            description: "File I/O sandbox with PDF/Excel libs pre-warmed"
        },
        browser: {
            prompt: "I need to extract the latest pricing table from an e-commerce website. I will use a headless browser with Playwright or Selenium to scrape the DOM elements and store results in a JSON file.",
            model: "llama3:8b",
            tool: "browser",
            threshold: 50,
            coldStart: 8.0,
            description: "Chromium headless browser container pre-warmed"
        },
        docker: {
            prompt: "We need to package the FastAPI microservice into a production Docker image. I will write a multi-stage Dockerfile, build it with docker buildx, tag it as v2.1.0, and push to the ECR registry. Let me draft the pipeline.",
            model: "llama3:8b",
            tool: "docker",
            threshold: 45,
            coldStart: 9.5,
            description: "Docker-in-Docker DinD runner container pre-warmed"
        },
        bash: {
            prompt: "The production server disk usage hit 94%. I need to write a bash script to identify the top 20 largest files under /var/log, compress logs older than 7 days with gzip, remove archives older than 30 days, and send a Slack webhook alert.",
            model: "llama3:8b",
            tool: "bash",
            threshold: 38,
            coldStart: 3.5,
            description: "Alpine Linux shell executor container pre-warmed"
        },
        api_test: {
            prompt: "I need to validate the new payments REST API. Let me write a test suite using httpx and pytest that hits POST /v1/charge, GET /v1/balance, and the GraphQL /graphql endpoint, checking status codes, response schemas, and latency SLAs.",
            model: "llama3:8b",
            tool: "python",
            threshold: 37,
            coldStart: 5.5,
            description: "API test runner with httpx/pytest pre-warmed"
        }
    };

    // State
    let activePods = [];
    let totalMaskedSeconds = 0.0;

    // Load initial preset
    function loadPreset(key) {
        const preset = PRESETS[key] || PRESETS.python;
        promptInput.value = preset.prompt;
        modelInput.value = preset.model;
        thresholdMarker.style.left = `${preset.threshold}%`;
        thresholdMarker.querySelector(".marker-label").innerText = `θ* (${(preset.threshold / 100).toFixed(2)})`;
        // Update latency comparison bar label dynamically
        const totalTrad = 8.5 + preset.coldStart;
        document.querySelector(".comp-bar-fill.fill-red").innerText =
            `${totalTrad.toFixed(1)}s (LLM 8.5s + Cold Start ${preset.coldStart.toFixed(1)}s)`;
        document.getElementById("streamops-bar-fill").style.width = `${(8.5 / totalTrad * 100).toFixed(0)}%`;
        document.getElementById("streamops-bar-fill").innerText = `8.5s (0s Cold Start — Fully Masked!)`;
        // Show the tool description as a subtitle under the stream box
        let descEl = document.getElementById("scenario-description");
        if (!descEl) {
            descEl = document.createElement("div");
            descEl.id = "scenario-description";
            descEl.style.cssText = "font-size:0.75rem;color:#94a3b8;margin-top:4px;font-style:italic;";
            document.querySelector(".stream-header").appendChild(descEl);
        }
        descEl.innerText = `💡 ${preset.description || ""}`;
    }

    presetSelector.addEventListener("change", (e) => {
        loadPreset(e.target.value);
    });

    loadPreset("python");

    // Execute Stream
    btnRunStream.addEventListener("click", async () => {
        const prompt = promptInput.value.trim();
        const model = modelInput.value.trim() || "llama3:8b";
        if (!prompt) return;

        // Reset UI State
        tokenStreamBox.innerHTML = "";
        streamStatus.innerText = "STREAMING...";
        streamStatus.className = "badge-status streaming";
        btnRunStream.disabled = true;
        confidenceBar.style.width = "0%";
        confidencePercentage.innerText = "0%";
        detectedToolName.innerText = "None";
        detectedToolName.className = "text-amber";
        finopsDecision.innerText = "Evaluating Lookahead...";
        intentStageBadge.innerText = "Stage 1: Ingestion";

        let currentConfidence = 0;
        let triggered = false;
        let spawnedPodName = null;
        let startTime = performance.now();

        try {
            const response = await fetch("/api/generate", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ prompt, model, stream: true })
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder("utf-8");
            let buffer = "";

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                const textChunk = decoder.decode(value, { stream: true });
                buffer += textChunk;
                
                // Process stream lines
                const lines = buffer.split("\n");
                buffer = lines.pop(); // Keep partial line

                for (const line of lines) {
                    if (!line.trim()) continue;
                    try {
                        const data = JSON.parse(line);
                        const word = data.response || (data.message && data.message.content) || "";
                        
                        if (word) {
                            renderToken(word);
                            
                            // Client-side visual lookahead simulation
                            const lower = word.toLowerCase();
                            if (lower.includes("python") || lower.includes("pandas") || lower.includes("script") ||
                                lower.includes("pdfplumber") || lower.includes("openpyxl") || lower.includes("httpx") ||
                                lower.includes("pytest") || lower.includes("torch") || lower.includes("dataloader")) {
                                updateConfidence("python", 0.78, "Stage 1: N-Gram Fast-Path");
                            } else if (lower.includes("sql") || lower.includes("postgres") || lower.includes("query") || lower.includes("select") || lower.includes("join")) {
                                updateConfidence("sql", 0.82, "Stage 1: N-Gram Fast-Path");
                            } else if (lower.includes("browser") || lower.includes("scrape") || lower.includes("selenium") || lower.includes("playwright") || lower.includes("chromium")) {
                                updateConfidence("browser", 0.75, "Stage 2: Vector Scorer");
                            } else if (lower.includes("redis") || lower.includes("cache") || lower.includes("ttl") || lower.includes("redis-py") || lower.includes("scan")) {
                                updateConfidence("redis", 0.80, "Stage 1: N-Gram Fast-Path");
                            } else if (lower.includes("docker") || lower.includes("dockerfile") || lower.includes("buildx") || lower.includes("ecr") || lower.includes("registry")) {
                                updateConfidence("docker", 0.83, "Stage 2: Vector Scorer");
                            } else if (lower.includes("bash") || lower.includes("shell") || lower.includes("gzip") || lower.includes("/var/log") || lower.includes("cron")) {
                                updateConfidence("bash", 0.77, "Stage 1: N-Gram Fast-Path");
                            } else if (lower.includes("graphql") || lower.includes("rest") || lower.includes("api") || lower.includes("endpoint") || lower.includes("webhook")) {
                                updateConfidence("api_test", 0.79, "Stage 2: Vector Scorer");
                            } else if (lower.includes("pytorch") || lower.includes("bert") || lower.includes("fine-tune") || lower.includes("epoch") || lower.includes("gpu")) {
                                updateConfidence("ml_training", 0.85, "Stage 3: Contextual LLM Scorer");
                            }
                        }
                    } catch (err) {
                        // Raw text fallback
                        renderToken(line);
                    }
                }
            }

        } catch (err) {
            console.error("Stream error:", err);
            // If proxy is offline, run demo simulation
            await runFallbackSimulation(prompt);
        } finally {
            streamStatus.innerText = "COMPLETED";
            streamStatus.className = "badge-status";
            btnRunStream.disabled = false;
            
            // Finalize Claim
            if (spawnedPodName) {
                claimPod(spawnedPodName);
            }
        }
    });

    function renderToken(text) {
        const span = document.createElement("span");
        if (text.includes("python") || text.includes("sql") || text.includes("browser") || text.includes("pandas")) {
            span.className = "token-intent";
        } else if (text.startsWith("<think>") || text.includes("think")) {
            span.className = "token-reasoning";
        }
        span.innerText = text;
        tokenStreamBox.appendChild(span);
        tokenStreamBox.scrollTop = tokenStreamBox.scrollHeight;
    }

    function updateConfidence(tool, score, stage) {
        const pct = Math.round(score * 100);
        confidenceBar.style.width = `${pct}%`;
        confidencePercentage.innerText = `${pct}%`;
        detectedToolName.innerText = tool.toUpperCase();
        detectedToolName.className = "text-emerald";
        intentStageBadge.innerText = stage;
        finopsDecision.innerHTML = `<span class="text-emerald">⚡ TRIGGER SPECULATION (θ* exceeded)</span>`;

        // Spawn Pod
        if (!activePods.some(p => p.tool === tool && p.status !== "Terminated")) {
            const sid = Math.random().toString(36).substring(2, 7);
            const podName = `streamops-${tool}-${sid}`;
            addPod(podName, tool);
        }
    }

    function addPod(podName, tool) {
        const pod = {
            name: podName,
            tool: tool,
            status: "ContainerCreating",
            createdAt: Date.now()
        };
        activePods.unshift(pod);
        renderPods();

        // Simulate fast K8s boot
        setTimeout(() => {
            pod.status = "Running";
            renderPods();
            totalMaskedSeconds += 5.5;
            totalLatencyMasked.innerText = `${totalMaskedSeconds.toFixed(1)}s`;
        }, 1200);
    }

    function claimPod(podName) {
        const pod = activePods.find(p => p.name === podName);
        if (pod) {
            pod.status = "Claimed";
            renderPods();
        }
    }

    function renderPods() {
        if (activePods.length === 0) {
            podListContainer.innerHTML = `<div class="empty-pod-notice">No speculative pods provisioned yet.</div>`;
            activePodCount.innerText = "0 Active";
            return;
        }

        activePodCount.innerText = `${activePods.length} Active`;
        podListContainer.innerHTML = activePods.map(p => {
            const badgeClass = p.status === "Running" ? "badge-running" : (p.status === "Claimed" ? "badge-claimed" : "badge-creating");
            const cardClass = p.status.toLowerCase();
            return `
                <div class="pod-card ${cardClass}">
                    <div class="pod-details">
                        <span class="pod-name">${p.name}</span>
                        <span class="pod-meta">Tool: ${p.tool} • Namespace: default • TTL: 60s</span>
                    </div>
                    <span class="pod-badge ${badgeClass}">${p.status}</span>
                </div>
            `;
        }).join("");
    }

    async function runFallbackSimulation(prompt) {
        const words = prompt.split(" ");
        const lower = prompt.toLowerCase();
        let tool = "python";
        let confidence = 0.85;
        let stage = "Stage 1: N-Gram Fast-Path";

        // Detect tool from prompt keywords
        if (lower.includes("sql") || lower.includes("postgres") || lower.includes("database")) { tool = "sql"; confidence = 0.82; }
        else if (lower.includes("browser") || lower.includes("scrape") || lower.includes("selenium") || lower.includes("playwright")) { tool = "browser"; confidence = 0.75; stage = "Stage 2: Vector Scorer"; }
        else if (lower.includes("redis") || lower.includes("cache") || lower.includes("ttl")) { tool = "redis"; confidence = 0.80; }
        else if (lower.includes("docker") || lower.includes("dockerfile") || lower.includes("buildx")) { tool = "docker"; confidence = 0.83; stage = "Stage 2: Vector Scorer"; }
        else if (lower.includes("bash") || lower.includes("shell") || lower.includes("gzip")) { tool = "bash"; confidence = 0.77; }
        else if (lower.includes("graphql") || lower.includes("rest") || lower.includes("httpx")) { tool = "api_test"; confidence = 0.79; stage = "Stage 2: Vector Scorer"; }
        else if (lower.includes("pytorch") || lower.includes("bert") || lower.includes("epoch") || lower.includes("gpu")) { tool = "ml_training"; confidence = 0.85; stage = "Stage 3: Contextual LLM Scorer"; }
        else if (lower.includes("pdf") || lower.includes("excel") || lower.includes("openpyxl")) { tool = "python"; confidence = 0.78; }

        const triggerAt = Math.min(6, Math.floor(words.length * 0.25));

        for (let i = 0; i < words.length; i++) {
            renderToken(words[i] + " ");
            await new Promise(r => setTimeout(r, 65));

            if (i === triggerAt) {
                updateConfidence(tool, confidence, stage);
            }
        }
    }
});

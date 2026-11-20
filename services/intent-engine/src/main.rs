use std::collections::HashMap;
use std::env;
use std::sync::Arc;
use std::time::{Duration, Instant};

use axum::extract::State;
use axum::http::StatusCode;
use axum::routing::{get, post};
use axum::{Json, Router};
use serde::{Deserialize, Serialize};
use tokio::net::TcpListener;
use tokio::sync::Mutex;

const SESSION_TTL: Duration = Duration::from_secs(900);
const MAX_BUFFER_BYTES: usize = 8192;
const STOP_WORDS: &[&str] = &[
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "i", "in", "is", "it", "me",
    "of", "on", "or", "that", "the", "this", "to", "will", "with", "you",
];

#[derive(Clone, Copy)]
struct ToolProfile {
    name: &'static str,
    description: &'static str,
    keywords: &'static [&'static str],
    cost_per_second_usd: f64,
    cold_start_seconds: f64,
    latency_penalty_usd_per_second: f64,
    ttl_seconds: f64,
}

const TOOLS: &[ToolProfile] = &[
    ToolProfile {
        name: "python",
        description: "execute python code run scripts use pandas for data analysis math calculations and matplotlib plotting",
        keywords: &[
            "python",
            "pandas",
            "numpy",
            "dataframe",
            "matplotlib",
            "scikit",
            "csv",
            "script",
            "repl",
            "code interpreter",
        ],
        cost_per_second_usd: 0.00005,
        cold_start_seconds: 5.5,
        latency_penalty_usd_per_second: 0.005,
        ttl_seconds: 60.0,
    },
    ToolProfile {
        name: "sql",
        description: "execute sql queries against a database postgres query relational database access",
        keywords: &[
            "sql",
            "select",
            "postgres",
            "postgresql",
            "database",
            "query",
            "schema",
            "table",
            "join",
            "sqlite",
        ],
        cost_per_second_usd: 0.00008,
        cold_start_seconds: 6.0,
        latency_penalty_usd_per_second: 0.005,
        ttl_seconds: 60.0,
    },
    ToolProfile {
        name: "browser",
        description: "search the web scrape webpages browse the internet using a headless browser or selenium",
        keywords: &[
            "browser",
            "scrape",
            "scraping",
            "playwright",
            "selenium",
            "headless",
            "html",
            "webpage",
            "crawl",
            "url",
        ],
        cost_per_second_usd: 0.00020,
        cold_start_seconds: 8.0,
        latency_penalty_usd_per_second: 0.005,
        ttl_seconds: 60.0,
    },
    ToolProfile {
        name: "bash",
        description: "execute bash shell commands terminal scripts system automation",
        keywords: &[
            "bash",
            "terminal",
            "curl",
            "grep",
            "chmod",
            "system command",
            "shell script",
        ],
        cost_per_second_usd: 0.00003,
        cold_start_seconds: 3.0,
        latency_penalty_usd_per_second: 0.005,
        ttl_seconds: 60.0,
    },
];

#[derive(Default)]
struct IntentEngine {
    buffer: String,
    triggered: bool,
}

#[derive(Default)]
struct AppState {
    sessions: Mutex<HashMap<String, Session>>,
}

struct Session {
    engine: IntentEngine,
    updated_at: Instant,
}

#[derive(Deserialize)]
struct ChunkRequest {
    session_id: String,
    text: String,
    #[serde(default)]
    is_reasoning: bool,
}

#[derive(Serialize)]
struct Decision {
    should_trigger: bool,
    tool_name: Option<&'static str>,
    confidence: f64,
    threshold: f64,
    detection_stage: Option<&'static str>,
    matched_keywords: Vec<&'static str>,
}

impl IntentEngine {
    fn process_chunk(&mut self, text: &str, is_reasoning: bool) -> Decision {
        if self.triggered || text.trim().is_empty() {
            return Decision::no_match();
        }

        self.buffer.push(' ');
        self.buffer.push_str(&normalize(text));
        trim_buffer(&mut self.buffer);

        if self.buffer.split_whitespace().count() < 2 {
            return Decision::no_match();
        }

        if let Some((tool, matched)) = fast_keyword_match(&self.buffer) {
            let confidence = (matched.len() as f64 * 0.4).min(1.0);
            let threshold = optimal_threshold(tool);
            if confidence >= threshold {
                self.triggered = true;
                return Decision {
                    should_trigger: true,
                    tool_name: Some(tool.name),
                    confidence,
                    threshold,
                    detection_stage: Some("keyword"),
                    matched_keywords: matched,
                };
            }
        }

        if self.buffer.split_whitespace().count() < 6 {
            return Decision::no_match();
        }

        let (tool, score) = best_tfidf_match(&self.buffer);
        let confidence = (score * if is_reasoning { 1.25 } else { 1.0 }).min(1.0);
        let threshold = optimal_threshold(tool);
        if confidence >= threshold {
            self.triggered = true;
            return Decision {
                should_trigger: true,
                tool_name: Some(tool.name),
                confidence,
                threshold,
                detection_stage: Some("tfidf"),
                matched_keywords: Vec::new(),
            };
        }

        Decision::no_match()
    }
}

impl Decision {
    fn no_match() -> Self {
        Self {
            should_trigger: false,
            tool_name: None,
            confidence: 0.0,
            threshold: 0.0,
            detection_stage: None,
            matched_keywords: Vec::new(),
        }
    }
}

fn optimal_threshold(tool: &ToolProfile) -> f64 {
    let waste = tool.cost_per_second_usd * tool.ttl_seconds;
    let cold_start_penalty = tool.cold_start_seconds * tool.latency_penalty_usd_per_second;
    (waste / (waste + cold_start_penalty)).clamp(0.15, 0.90)
}

fn normalize(text: &str) -> String {
    text.to_lowercase()
        .chars()
        .map(|ch| if ch.is_alphanumeric() { ch } else { ' ' })
        .collect()
}

fn trim_buffer(buffer: &mut String) {
    if buffer.len() <= MAX_BUFFER_BYTES {
        return;
    }
    let mut start = buffer.len() - MAX_BUFFER_BYTES;
    while !buffer.is_char_boundary(start) {
        start += 1;
    }
    buffer.drain(..start);
}

fn fast_keyword_match(buffer: &str) -> Option<(&'static ToolProfile, Vec<&'static str>)> {
    for tool in TOOLS {
        let matched: Vec<_> = tool
            .keywords
            .iter()
            .copied()
            .filter(|keyword| {
                let phrase = normalize(keyword);
                let buffer = buffer.split_whitespace().collect::<Vec<_>>();
                let phrase: Vec<_> = phrase.split_whitespace().collect();
                if phrase.is_empty() {
                    return false;
                }
                buffer
                    .windows(phrase.len())
                    .any(|window| window == phrase.as_slice())
            })
            .collect();
        if !matched.is_empty() {
            return Some((tool, matched));
        }
    }
    None
}

fn ngrams(text: &str) -> HashMap<String, usize> {
    let words: Vec<_> = normalize(text)
        .split_whitespace()
        .filter(|word| !STOP_WORDS.contains(word))
        .map(str::to_owned)
        .collect();
    let mut counts = HashMap::new();
    for word in &words {
        *counts.entry(word.clone()).or_insert(0) += 1;
    }
    for pair in words.windows(2) {
        *counts
            .entry(format!("{} {}", pair[0], pair[1]))
            .or_insert(0) += 1;
    }
    counts
}

fn best_tfidf_match(query: &str) -> (&'static ToolProfile, f64) {
    let query_terms = ngrams(query);
    if query_terms.is_empty() {
        return (&TOOLS[0], 0.0);
    }

    let documents: Vec<_> = TOOLS
        .iter()
        .map(|tool| ngrams(&format!("{} {}", tool.description, tool.keywords.join(" "))))
        .collect();
    let document_frequency: HashMap<String, usize> = {
        let mut frequencies = HashMap::new();
        for document in &documents {
            for term in document.keys() {
                *frequencies.entry(term.clone()).or_insert(0) += 1;
            }
        }
        frequencies
    };

    let total_documents = documents.len() as f64;
    let mut query_vector = HashMap::new();
    for (term, count) in query_terms {
        if let Some(df) = document_frequency.get(&term) {
            let tf = 1.0 + (count as f64).ln();
            let idf = ((1.0 + total_documents) / (1.0 + *df as f64)).ln() + 1.0;
            query_vector.insert(term, tf * idf);
        }
    }

    let query_norm = query_vector
        .values()
        .map(|value| value * value)
        .sum::<f64>()
        .sqrt();
    if query_norm == 0.0 {
        return (&TOOLS[0], 0.0);
    }

    let mut best = (&TOOLS[0], 0.0);
    for (tool, document) in TOOLS.iter().zip(documents.iter()) {
        let mut dot = 0.0;
        let mut document_norm_squared = 0.0;
        for (term, count) in document {
            let df = document_frequency[term] as f64;
            let tf = 1.0 + (*count as f64).ln();
            let idf = ((1.0 + total_documents) / (1.0 + df)).ln() + 1.0;
            let weight = tf * idf;
            document_norm_squared += weight * weight;
            if let Some(query_weight) = query_vector.get(term) {
                dot += query_weight * weight;
            }
        }
        let norm = document_norm_squared.sqrt();
        let score = if norm == 0.0 {
            0.0
        } else {
            dot / (query_norm * norm)
        };
        if score > best.1 {
            best = (tool, score);
        }
    }
    best
}

async fn healthz() -> &'static str {
    "ok"
}

async fn detect(
    State(state): State<Arc<AppState>>,
    Json(request): Json<ChunkRequest>,
) -> Result<Json<Decision>, (StatusCode, String)> {
    let session_id = request.session_id.trim();
    if session_id.is_empty() || session_id.len() > 128 {
        return Err((
            StatusCode::BAD_REQUEST,
            "session_id must be 1-128 characters".into(),
        ));
    }

    let mut sessions = state.sessions.lock().await;
    let now = Instant::now();
    sessions.retain(|_, session| now.duration_since(session.updated_at) < SESSION_TTL);
    let session = sessions
        .entry(session_id.to_owned())
        .or_insert_with(|| Session {
            engine: IntentEngine::default(),
            updated_at: now,
        });
    session.updated_at = now;
    Ok(Json(
        session
            .engine
            .process_chunk(&request.text, request.is_reasoning),
    ))
}

async fn reset(
    State(state): State<Arc<AppState>>,
    Json(request): Json<ResetRequest>,
) -> Result<StatusCode, (StatusCode, String)> {
    let session_id = request.session_id.trim();
    if session_id.is_empty() || session_id.len() > 128 {
        return Err((
            StatusCode::BAD_REQUEST,
            "session_id must be 1-128 characters".into(),
        ));
    }
    state.sessions.lock().await.remove(session_id);
    Ok(StatusCode::NO_CONTENT)
}

#[derive(Deserialize)]
struct ResetRequest {
    session_id: String,
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let address = env::var("INTENT_LISTEN_ADDR").unwrap_or_else(|_| "0.0.0.0:8081".into());
    let listener = TcpListener::bind(&address).await?;
    let state = Arc::new(AppState::default());
    let app = Router::new()
        .route("/healthz", get(healthz))
        .route("/v1/chunks", post(detect))
        .route("/v1/reset", post(reset))
        .with_state(state);

    eprintln!("intent engine listening on {address}");
    axum::serve(listener, app).await?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn triggers_once_for_keyword_and_respects_cost_threshold() {
        let mut engine = IntentEngine::default();
        let first = engine.process_chunk("I need to use ", true);
        assert!(!first.should_trigger);

        let decision = engine.process_chunk("python and pandas", true);
        assert!(decision.should_trigger);
        assert_eq!(decision.tool_name, Some("python"));
        assert_eq!(decision.detection_stage, Some("keyword"));
        assert!(decision.confidence >= decision.threshold);
        assert!(!engine.process_chunk("now use SQL", false).should_trigger);
    }

    #[test]
    fn scores_semantic_terms_with_tfidf_when_no_keyword_matches() {
        let mut engine = IntentEngine::default();
        let decision =
            engine.process_chunk("I need to retrieve rows from a relational store", false);
        assert!(decision.should_trigger);
        assert_eq!(decision.tool_name, Some("sql"));
        assert_eq!(decision.detection_stage, Some("tfidf"));
    }

    #[test]
    fn bayesian_threshold_uses_waste_and_cold_start_costs() {
        let python = &TOOLS[0];
        let expected = (python.cost_per_second_usd * python.ttl_seconds)
            / (python.cost_per_second_usd * python.ttl_seconds
                + python.cold_start_seconds * python.latency_penalty_usd_per_second);
        assert!((optimal_threshold(python) - expected.max(0.15)).abs() < 1e-12);
    }

    #[test]
    fn buffer_keeps_a_utf8_safe_rolling_window() {
        let mut buffer = "🙂".repeat(MAX_BUFFER_BYTES);
        trim_buffer(&mut buffer);
        assert!(buffer.len() <= MAX_BUFFER_BYTES);
        assert!(buffer.is_char_boundary(0));
    }
}

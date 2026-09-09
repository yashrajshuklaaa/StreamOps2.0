import json
import logging
import os
import re
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .finops_optimizer import FinOpsOptimizer

logger = logging.getLogger("streamops.intent")

@dataclass
class IntentMatchResult:
    tool_name: str
    confidence: float
    threshold: float
    should_trigger: bool
    detection_stage: str
    matched_keywords: List[str]


class IntentDetector:
    """
    Multi-stage, calibrated intent detector for streaming Chain-of-Thought lookahead.
    Combines n-gram fast-filtering, TF-IDF semantic vector similarity, and FinOps thresholding.
    """

    DEFAULT_KEYWORDS: Dict[str, List[str]] = {
        "python": ["python", "pandas", "numpy", "dataframe", "matplotlib", "scikit", "csv", "script", "repl", "code interpreter"],
        "sql": ["sql", "select", "postgres", "postgresql", "database", "query", "schema", "table", "join", "sqlite"],
        "browser": ["browser", "scrape", "scraping", "playwright", "selenium", "headless", "html", "webpage", "crawl", "url"],
        "bash": ["bash", "sh", "terminal", "curl", "grep", "chmod", "system command", "shell script"]
    }

    def __init__(
        self,
        registry_path: str = "tools_registry.json",
        finops_optimizer: Optional[FinOpsOptimizer] = None,
        base_threshold: float = 0.30
    ):
        self.registry_path = registry_path
        self.finops = finops_optimizer or FinOpsOptimizer()
        self.base_threshold = base_threshold
        self.buffer = ""
        self.triggered_tool: Optional[str] = None
        self.token_count = 0

        # Load tool registry
        self.registry: Dict[str, Any] = self._load_registry()
        self.tool_names = list(self.registry.keys())

        # Compile rich corpus for each tool combining description + keywords
        self.tool_corpus = []
        for tool in self.tool_names:
            desc = self.registry[tool].get("description", "")
            keywords = " ".join(self.DEFAULT_KEYWORDS.get(tool, []))
            self.tool_corpus.append(f"{desc} {keywords} {tool}")

        # Initialize TF-IDF Vectorizer with ngram range (1, 2)
        self.vectorizer = TfidfVectorizer(
            stop_words="english",
            ngram_range=(1, 2),
            sublinear_tf=True
        )
        self.tfidf_matrix = self.vectorizer.fit_transform(self.tool_corpus)
        logger.info(f"IntentDetector initialized with {len(self.tool_names)} tools and TF-IDF matrix {self.tfidf_matrix.shape}.")

    def _load_registry(self) -> Dict[str, Any]:
        if os.path.exists(self.registry_path):
            try:
                with open(self.registry_path, "r") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Error loading {self.registry_path}: {e}")

        # Fallback default registry
        return {
            "python": {
                "description": "Execute python code, run scripts, use pandas for data analysis, math calculations, and matplotlib for plotting.",
                "sandbox_image": "python:3.11-slim",
                "cpu_limit": "500m",
                "memory_limit": "512Mi"
            },
            "sql": {
                "description": "Execute SQL queries against a database, postgres query, relational database access.",
                "sandbox_image": "postgres:15-alpine",
                "cpu_limit": "500m",
                "memory_limit": "512Mi"
            },
            "browser": {
                "description": "Search the web, scrape webpages, browse the internet using a headless browser or selenium.",
                "sandbox_image": "selenium/standalone-chrome:latest",
                "cpu_limit": "1000m",
                "memory_limit": "1Gi"
            },
            "bash": {
                "description": "Execute bash shell commands, terminal scripts, system automation.",
                "sandbox_image": "alpine:latest",
                "cpu_limit": "250m",
                "memory_limit": "256Mi"
            }
        }

    def process_chunk(self, text_chunk: str, is_reasoning: bool = False) -> Optional[IntentMatchResult]:
        """
        Ingests a streaming chunk. If intent confidence crosses the FinOps optimal threshold,
        returns an IntentMatchResult triggering speculative provisioning.
        """
        if self.triggered_tool:
            return None

        if not text_chunk:
            return None

        self.buffer += " " + text_chunk.lower()
        self.token_count += len(text_chunk.split())

        words = self.buffer.split()
        if len(words) < 2:
            return None

        # Stage 1: Ultra-fast keyword exact matching check
        stage1_match = self._check_fast_keywords(self.buffer)
        if stage1_match:
            tool, kw_score, matched_kws = stage1_match
            threshold = self.finops.get_threshold(tool, self.base_threshold)
            if kw_score >= threshold:
                self.triggered_tool = tool
                logger.info(f"⚡ [Stage 1 Fast-Path] Intent matched: {tool} (Score: {kw_score:.2f} >= {threshold:.2f})")
                return IntentMatchResult(
                    tool_name=tool,
                    confidence=kw_score,
                    threshold=threshold,
                    should_trigger=True,
                    detection_stage="Stage 1: N-Gram Fast Filter",
                    matched_keywords=matched_kws
                )

        # Stage 2: TF-IDF Cosine Similarity Vector Scorer
        try:
            buffer_vec = self.vectorizer.transform([self.buffer])
            similarities = cosine_similarity(buffer_vec, self.tfidf_matrix)[0]
            best_idx = similarities.argmax()
            raw_score = float(similarities[best_idx])
            tool = self.tool_names[best_idx]

            # Boost confidence if tokens were generated inside explicit reasoning block (CoT)
            calibrated_score = min(1.0, raw_score * (1.25 if is_reasoning else 1.0))
            threshold = self.finops.get_threshold(tool, self.base_threshold)

            if calibrated_score >= threshold:
                self.triggered_tool = tool
                logger.info(f"⚡ [Stage 2 TF-IDF] Intent matched: {tool} (Score: {calibrated_score:.2f} >= {threshold:.2f})")
                return IntentMatchResult(
                    tool_name=tool,
                    confidence=calibrated_score,
                    threshold=threshold,
                    should_trigger=True,
                    detection_stage="Stage 2: Vector Similarity",
                    matched_keywords=[]
                )

        except ValueError:
            pass

        return None

    def _check_fast_keywords(self, text: str) -> Optional[tuple]:
        """Calculates fast-path n-gram keyword presence."""
        for tool, keywords in self.DEFAULT_KEYWORDS.items():
            matched = [kw for kw in keywords if re.search(r'\b' + re.escape(kw) + r'\b', text)]
            if matched:
                # Cumulative score based on matched keyword count (each match adds 0.35)
                score = min(1.0, len(matched) * 0.40)
                return tool, score, matched
        return None

    def reset(self):
        """Resets the detector state for a new stream session."""
        self.buffer = ""
        self.triggered_tool = None
        self.token_count = 0

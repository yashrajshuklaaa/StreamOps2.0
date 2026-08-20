import logging
import json
import os
from typing import Optional
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger("IntentDetector")

class IntentDetector:
    """
    Analyzes streaming text to detect tool/infrastructure intents using
    TF-IDF Vectorization and Cosine Similarity against a dynamic JSON Tool Registry.
    """
    def __init__(self, threshold: float = 0.2, registry_path: str = "tools_registry.json"):
        self.threshold = threshold
        self.buffer = ""
        self.triggered_tool: Optional[str] = None
        
        # Load the dynamic tool registry
        if not os.path.exists(registry_path):
            raise FileNotFoundError(f"Could not find Tool Registry at {registry_path}")
            
        with open(registry_path, "r") as f:
            self.registry = json.load(f)
            
        self.tool_names = list(self.registry.keys())
        # We use the descriptions as the semantic 'corpus'
        self.tool_descriptions = [self.registry[tool]["description"] for tool in self.tool_names]
        
        # Initialize the TF-IDF Vectorizer and fit it to our tool descriptions
        # stop_words="english" removes common words like 'the', 'is', 'at'
        self.vectorizer = TfidfVectorizer(stop_words="english")
        self.tfidf_matrix = self.vectorizer.fit_transform(self.tool_descriptions)
        
        logger.info(f"IntentDetector initialized with {len(self.tool_names)} tools from registry.")

    def process_chunk(self, text: str) -> Optional[str]:
        """
        Ingests a new chunk of text and computes cosine similarity against the tool registry.
        If similarity > threshold, returns the tool name.
        """
        if self.triggered_tool:
            return None
            
        self.buffer += text.lower()
        
        # We need a minimum amount of text to make a semantic judgment (e.g., at least 3 words)
        if len(self.buffer.split()) < 3:
            return None
            
        try:
            # Vectorize the current streaming buffer
            buffer_vector = self.vectorizer.transform([self.buffer])
            
            # Compute cosine similarity between the buffer and all tool descriptions
            similarities = cosine_similarity(buffer_vector, self.tfidf_matrix)[0]
            
            # Find the best matching tool
            best_match_idx = similarities.argmax()
            best_score = similarities[best_match_idx]
            
            if best_score >= self.threshold:
                self.triggered_tool = self.tool_names[best_match_idx]
                logger.info(f"IntentDetector: '{self.triggered_tool}' matched with Cosine Similarity {best_score:.2f}")
                return self.triggered_tool
                
        except ValueError:
            # Raised if the buffer only contains stop words (e.g. "I will use ")
            pass
            
        return None

    def reset(self):
        """Resets the detector for a new stream."""
        self.buffer = ""
        self.triggered_tool = None

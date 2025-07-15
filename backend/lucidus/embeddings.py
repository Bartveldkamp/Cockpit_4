import logging
from sentence_transformers import SentenceTransformer, util

logger = logging.getLogger(__name__)

class EmbeddingModel:
    def __init__(self, model_name="all-MiniLM-L6-v2"):
        self.model = None
        self.load_model(model_name)

    def load_model(self, model_name):
        try:
            self.model = SentenceTransformer(model_name)
        except Exception as e:
            logger.error(f"Could not load SentenceTransformer model: {e}")
            self.model = None

    def encode(self, text):
        if self.model is None:
            logger.error("Embedding model is not loaded.")
            return None
        return self.model.encode(text, convert_to_tensor=True)

embedding_model = EmbeddingModel()

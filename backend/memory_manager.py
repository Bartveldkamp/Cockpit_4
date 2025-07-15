import chromadb
from sentence_transformers import SentenceTransformer
import logging
from typing import List

from backend.config import settings

logger = logging.getLogger(__name__)

class MemoryManager:
    """Handles the agent's long-term memory using a vector database."""

    def __init__(self):
        """Initializes the MemoryManager, loading the embedding model and database."""
        try:
            self.model = SentenceTransformer(settings.embedding_model)
            self._db_client = chromadb.PersistentClient(path=settings.chroma_path)
            self.collection = self._db_client.get_or_create_collection(name=settings.collection_name)
            logger.info("MemoryManager initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize MemoryManager: {e}", exc_info=True)
            self.model = None
            self.collection = None

    def add_to_memory(self, content: str, filename: str, session_id: str):
        """Adds a file's content to the long-term memory."""
        if not self.model or not self.collection:
            logger.error("Cannot add to memory, MemoryManager not initialized.")
            return

        try:
            # The document ID must be unique. We'll use session_id + filename.
            doc_id = f"{session_id}:{filename}"
            embedding = self.model.encode(content).tolist()

            self.collection.upsert(
                ids=[doc_id],
                embeddings=[embedding],
                documents=[content],
                metadatas=[{"filename": filename, "session_id": session_id}]
            )
            logger.info(f"Successfully added '{filename}' to long-term memory.")
        except Exception as e:
            logger.error(f"Failed to add '{filename}' to memory: {e}", exc_info=True)

    def retrieve_from_memory(self, query_text: str, n_results: int = 3) -> List[str]:
        """Retrieves the most relevant documents from memory based on a query."""
        if not self.model or not self.collection or not query_text:
            return []

        try:
            query_embedding = self.model.encode(query_text).tolist()
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results
            )

            retrieved_docs = results.get('documents', [[]])[0]
            logger.info(f"Retrieved {len(retrieved_docs)} documents from memory.")
            return retrieved_docs
        except Exception as e:
            logger.error(f"Failed to retrieve from memory: {e}", exc_info=True)
            return []

# Create a single, global instance of the MemoryManager
memory_manager = MemoryManager()

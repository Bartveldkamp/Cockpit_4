import logging
from sentence_transformers import util

logger = logging.getLogger(__name__)

def get_complexity_level(text: str) -> str:
    wc = len(text.split())
    if wc > 50:
        return "high"
    if wc > 20:
        return "medium"
    return "low"

def vector_match(response: str, embedding_model, vault, threshold: float = 0.5):
    if embedding_model.model is None:
        return []

    response_embedding = embedding_model.encode(response)
    hits = []
    for entry in vault:
        if "embedding" not in entry or entry["embedding"] is None:
            continue
        try:
            sim = util.cos_sim(response_embedding, entry["embedding"]).item()
            if sim >= threshold:
                hits.append({
                    "id": entry.get("id"),
                    "fact": entry.get("fact"),
                    "tags": entry.get("tags", []),
                    "source": entry.get("source"),
                    "similarity": round(sim, 3)
                })
        except Exception as e:
            logger.warning(f"Error during similarity calculation: {e}")
            continue
    return hits

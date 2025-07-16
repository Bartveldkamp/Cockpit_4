import json
import logging
from pathlib import Path
from backend.config import settings

logger = logging.getLogger(__name__)

class Vault:
    def __init__(self, vault_path="vault.coding.json"):
        self.vault_path = Path(__file__).resolve().parent / vault_path
        self.vault = self.load_vault()

    def load_vault(self):
        if not self.vault_path.exists():
            logger.warning(f"Vault file not found at {self.vault_path}. Lucidus will operate without vault data.")
            return []
        try:
            with open(self.vault_path, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            logger.error(f"Vault file at {self.vault_path} is not a valid JSON file.")
            return []

    def precompute_embeddings(self, embedding_model):
        for entry in self.vault:
            if "fact" in entry and "embedding" not in entry:
                entry["embedding"] = embedding_model.encode(entry["fact"])

vault = Vault()
vault.precompute_embeddings(settings.embedding_model)

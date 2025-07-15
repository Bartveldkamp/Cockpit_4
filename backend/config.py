import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    mistral_api_key: str
    mistral_api_url: str = "https://api.mistral.ai/v1/chat/completions"
    mistral_model: str = "mistral-large-latest"
    max_retries: int = 2
    embedding_model: str = "all-MiniLM-L6-v2"
    chroma_path: str = "memory_db"
    collection_name: str = "project_memory"
    vault_root: str = os.path.join(os.path.dirname(__file__), '..', 'vault_data')
    database_file: str = "cockpit.db"

settings = Settings()

import os
import sys
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # This line is crucial: it forces Pydantic to load the .env file.
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8')

    # --- Your required settings ---
    mistral_api_key: str

    # --- Your other settings with default values ---
    mistral_api_url: str = "https://api.mistral.ai/v1/chat/completions"
    mistral_model: str = "mistral-large-latest"
    max_retries: int = 2
    embedding_model: str = "all-MiniLM-L6-v2"
    chroma_path: str = "memory_db"
    collection_name: str = "project_memory"
    vault_root: str = os.path.join(os.path.dirname(__file__), '..', 'vault_data')
    database_file: str = "cockpit.db"

# This line reads the settings when the module is imported
settings = Settings()

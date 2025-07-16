import os
import pytest
from unittest.mock import patch
from backend.config import Settings

def test_settings_defaults():
    settings = Settings()
    assert settings.mistral_api_url == "https://api.mistral.ai/v1/chat/completions"
    assert settings.mistral_model == "mistral-large-latest"
    assert settings.max_retries == 2
    assert settings.embedding_model == "all-MiniLM-L6-v2"
    assert settings.chroma_path == "memory_db"
    assert settings.collection_name == "project_memory"
    assert settings.vault_root == os.path.join(os.path.dirname(__file__), '..', 'vault_data')
    assert settings.database_file == "cockpit.db"

def test_settings_from_env():
    with patch.dict(os.environ, {
        "MISTRAL_API_KEY": "test_api_key",
        "MISTRAL_API_URL": "https://test.api/v1/chat/completions",
        "MISTRAL_MODEL": "test-model",
        "MAX_RETRIES": "3",
        "EMBEDDING_MODEL": "test-embedding-model",
        "CHROMA_PATH": "test_memory_db",
        "COLLECTION_NAME": "test_project_memory",
        "VAULT_ROOT": "/test/vault",
        "DATABASE_FILE": "test_cockpit.db"
    }):
        settings = Settings()
        assert settings.mistral_api_key == "test_api_key"
        assert settings.mistral_api_url == "https://test.api/v1/chat/completions"
        assert settings.mistral_model == "test-model"
        assert settings.max_retries == 3
        assert settings.embedding_model == "test-embedding-model"
        assert settings.chroma_path == "test_memory_db"
        assert settings.collection_name == "test_project_memory"
        assert settings.vault_root == "/test/vault"
        assert settings.database_file == "test_cockpit.db"

def test_settings_missing_api_key():
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ValueError, match="MISTRAL_API_KEY"):
            Settings()

def test_settings_partial_env():
    with patch.dict(os.environ, {
        "MISTRAL_API_KEY": "test_api_key",
        "MISTRAL_API_URL": "https://test.api/v1/chat/completions"
    }):
        settings = Settings()
        assert settings.mistral_api_key == "test_api_key"
        assert settings.mistral_api_url == "https://test.api/v1/chat/completions"
        assert settings.mistral_model == "mistral-large-latest"
        assert settings.max_retries == 2
        assert settings.embedding_model == "all-MiniLM-L6-v2"
        assert settings.chroma_path == "memory_db"
        assert settings.collection_name == "project_memory"
        assert settings.vault_root == os.path.join(os.path.dirname(__file__), '..', 'vault_data')
        assert settings.database_file == "cockpit.db"


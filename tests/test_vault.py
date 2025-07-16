import os
import json
import pytest
from unittest.mock import patch, mock_open, call
from backend.vault import _update_manifest_entry, get_session_vault_path, ensure_vault_exists, VAULT_ROOT

# Mock settings for testing
@pytest.fixture(autouse=True)
def mock_settings():
    with patch('backend.vault.settings.vault_root', '/mock/vault/root'):
        yield

def test_get_session_vault_path():
    session_id = "test-session"
    expected_path = os.path.join('/mock/vault/root', session_id)
    assert get_session_vault_path(session_id) == expected_path

def test_ensure_vault_exists():
    session_id = "test-session"
    expected_path = os.path.join('/mock/vault/root', session_id)

    with patch('os.makedirs') as mock_makedirs:
        ensure_vault_exists(session_id)
        mock_makedirs.assert_called_once_with(expected_path, exist_ok=True)

def test_update_manifest_entry_new_file():
    session_id = "test-session"
    filename = "test_file.txt"
    session_vault_path = os.path.join('/mock/vault/root', session_id)
    manifest_path = os.path.join(session_vault_path, 'manifest.json')

    # Mock os.makedirs and open to simulate file system operations
    with patch('os.makedirs') as mock_makedirs:
        with patch('builtins.open', mock_open()) as mock_file:
            _update_manifest_entry(session_id, filename)

            # Ensure os.makedirs is called to create the session vault directory
            mock_makedirs.assert_called_once_with(session_vault_path, exist_ok=True)

            # Ensure the manifest file is created and updated correctly
            mock_file.assert_has_calls([
                call(manifest_path, 'w'),
                call().__enter__(),
                call().write(json.dumps([filename], indent=4)),
                call().__exit__(None, None, None)
            ])

def test_update_manifest_entry_existing_file():
    session_id = "test-session"
    filename = "test_file.txt"
    session_vault_path = os.path.join('/mock/vault/root', session_id)
    manifest_path = os.path.join(session_vault_path, 'manifest.json')

    # Mock os.makedirs and open to simulate file system operations
    with patch('os.makedirs') as mock_makedirs:
        with patch('os.path.exists', return_value=True):
            with patch('builtins.open', mock_open(read_data=json.dumps(["existing_file.txt"]))) as mock_file:
                _update_manifest_entry(session_id, filename)

                # Ensure os.makedirs is called to create the session vault directory
                mock_makedirs.assert_called_once_with(session_vault_path, exist_ok=True)

                # Ensure the manifest file is read and updated correctly
                mock_file.assert_has_calls([
                    call(manifest_path, 'r'),
                    call().__enter__(),
                    call().read(),
                    call().__exit__(None, None, None),
                    call(manifest_path, 'w'),
                    call().__enter__(),
                    call().write(json.dumps(["existing_file.txt", filename], indent=4)),
                    call().__exit__(None, None, None)
                ])

def test_update_manifest_entry_exception():
    session_id = "test-session"
    filename = "test_file.txt"
    session_vault_path = os.path.join('/mock/vault/root', session_id)
    manifest_path = os.path.join(session_vault_path, 'manifest.json')

    # Mock os.makedirs and open to simulate file system operations
    with patch('os.makedirs') as mock_makedirs:
        with patch('builtins.open', mock_open()) as mock_file:
            mock_file.side_effect = Exception("File operation failed")

            with patch('backend.vault.logger.error') as mock_logger_error:
                _update_manifest_entry(session_id, filename)

                # Ensure os.makedirs is called to create the session vault directory
                mock_makedirs.assert_called_once_with(session_vault_path, exist_ok=True)

                # Ensure the logger error is called
                mock_logger_error.assert_called_once_with(
                    f"Failed to update manifest for session '{session_id}': File operation failed",
                    exc_info=True
                )

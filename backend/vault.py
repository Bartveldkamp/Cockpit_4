import os
import logging
import json

from backend.config import settings

logger = logging.getLogger(__name__)

VAULT_ROOT = settings.vault_root

def _update_manifest_entry(session_id: str, filename: str):
    session_vault_path = os.path.join(VAULT_ROOT, session_id)
    manifest_path = os.path.join(session_vault_path, 'manifest.json')

    os.makedirs(session_vault_path, exist_ok=True)

    try:
        if os.path.exists(manifest_path):
            with open(manifest_path, 'r') as f:
                manifest = json.load(f)
        else:
            manifest = []

        manifest.append(filename)

        with open(manifest_path, 'w') as f:
            json.dump(manifest, f, indent=4)

        logger.info(f"Updated manifest for session '{session_id}' with file '{filename}'.")

    except Exception as e:
        logger.error(f"Failed to update manifest for session '{session_id}': {e}", exc_info=True)

def get_session_vault_path(session_id: str) -> str:
    return os.path.join(VAULT_ROOT, session_id)

def ensure_vault_exists(session_id: str) -> None:
    os.makedirs(get_session_vault_path(session_id), exist_ok=True)

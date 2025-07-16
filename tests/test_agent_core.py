# tests/test_agent_core.py
import pytest
import json
from unittest.mock import patch, AsyncMock
from backend.agent_core import run_agent

# Correct paths for patching objects imported and used within agent_core.py
MEMORY_MANAGER_PATCH_PATH = 'backend.agent_core.memory_manager.retrieve_from_memory'
LLM_CLIENT_PATCH_PATH = 'backend.agent_core.get_llm_response'
TOOLS_PATCH_PATH = 'backend.agent_core.execute_tool'
UTILS_CRITIC_PATCH_PATH = 'backend.agent_core.validate_plan_semantically'

@pytest.fixture(autouse=True)
def override_settings(tmp_path):
    with patch('backend.tools.VAULT_ROOT', str(tmp_path)):
        with patch('backend.agent_core.settings.max_retries', 1):
             yield

@pytest.mark.asyncio
async def test_run_agent_success(tmp_path):
    user_prompt = "Test success"
    session_id = "test-session-success"
    
    mock_plan = { "plan": [{"tool": {"name": "execute_script"}, "parameters": {"command": "echo success"}, "reason": "Test"}] }
    mock_plan_str = json.dumps(mock_plan)

    with patch(LLM_CLIENT_PATCH_PATH, new_callable=AsyncMock, return_value=mock_plan_str) as mock_llm:
        with patch(MEMORY_MANAGER_PATCH_PATH, return_value=[]) as mock_memory:
            with patch(UTILS_CRITIC_PATCH_PATH) as mock_critic:
                mock_critic.side_effect = lambda plan_list, *args, **kwargs: (True, "Test approval", plan_list)
                with patch(TOOLS_PATCH_PATH, new_callable=AsyncMock, return_value={"status": "success", "data": "Tools executed"}) as mock_execute:
                    result = await run_agent(user_prompt, session_id, [])
                    assert result['response'] == "Tools executed"

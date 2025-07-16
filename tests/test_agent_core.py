# tests/test_agent_core.py
import pytest
import json
from unittest.mock import patch, AsyncMock
from backend.agent_core import run_agent

# Correctly patch where memory_manager is used: in agent_core
MEMORY_MANAGER_PATCH_PATH = 'backend.agent_core.memory_manager.retrieve_from_memory'
LLM_CLIENT_PATCH_PATH = 'backend.agent_core.get_llm_response'
TOOLS_PATCH_PATH = 'backend.agent_core.execute_tool'

@pytest.fixture(autouse=True)
def override_settings(tmp_path):
    # This fixture provides a safe, temporary directory for tests that need a vault
    with patch('backend.tools.VAULT_ROOT', str(tmp_path)):
        with patch('backend.agent_core.settings.max_retries', 1): # Speeds up tests
             yield

@pytest.mark.asyncio
async def test_run_agent_success(tmp_path):
    user_prompt = "Create a test file."
    session_id = "test-session-success"
    
    mock_plan = { "plan": [{"tool": {"name": "execute_script"}, "parameters": {"command": "echo success"}, "reason": "Test"}] }
    mock_plan_str = json.dumps(mock_plan)

    with patch(LLM_CLIENT_PATCH_PATH, new_callable=AsyncMock, return_value=mock_plan_str):
        with patch(MEMORY_MANAGER_PATCH_PATH, return_value=[]):
            with patch('backend.utils.validate_plan_semantically') as mock_critic:
                mock_critic.side_effect = lambda plan_list, *args, **kwargs: (True, "Test approval", plan_list)
                with patch(TOOLS_PATCH_PATH, new_callable=AsyncMock, return_value={"status": "success", "data": "All tools ran."}) as mock_execute:
                    
                    result = await run_agent(user_prompt, session_id, [])
                    
                    assert result['response'] == "All tools ran."
                    mock_execute.assert_called_once()

@pytest.mark.asyncio
async def test_run_agent_plan_generation_failure():
    # This test checks if the agent correctly handles getting invalid JSON from the LLM
    with patch(LLM_CLIENT_PATCH_PATH, new_callable=AsyncMock, return_value="this is not json"):
        with patch(MEMORY_MANAGER_PATCH_PATH, return_value=[]):
            result = await run_agent("test", "test", [])
            assert "Invalid plan structure" in result['response']

@pytest.mark.asyncio
async def test_run_agent_execution_failure():
    # This test checks if the agent correctly handles a tool failing during execution
    mock_plan = { "plan": [{"tool": {"name": "execute_script"}, "parameters": {"command": "fail please"}, "reason": "Test"}] }
    mock_plan_str = json.dumps(mock_plan)
    
    with patch(LLM_CLIENT_PATCH_PATH, new_callable=AsyncMock, return_value=mock_plan_str):
        with patch(MEMORY_MANAGER_PATCH_PATH, return_value=[]):
            with patch('backend.utils.validate_plan_semantically') as mock_critic:
                mock_critic.side_effect = lambda plan_list, *args, **kwargs: (True, "Test approval", plan_list)
                # Mock the tool to return an error
                with patch(TOOLS_PATCH_PATH, new_callable=AsyncMock, return_value={"status": "error", "message": "Tool failed"}):
                    result = await run_agent("test", "test", [])
                    assert "Tool failed" in result['response']

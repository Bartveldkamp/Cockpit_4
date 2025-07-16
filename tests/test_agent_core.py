import pytest
import json
from unittest.mock import patch, AsyncMock
from backend.agent_core import run_agent

@pytest.mark.asyncio
async def test_run_agent_success():
    user_prompt = "Create a new directory called 'my_test_project'."
    session_id = "test-session-id"
    chat_history = []

    mock_plan_json_string = json.dumps({
        "plan": [
            {
                "tool": {"name": "execute_script"},
                "parameters": {"command": "mkdir my_test_project"},
                "reason": "Create a new directory for the Python project."
            },
            {
                "tool": {"name": "execute_script"},
                "parameters": {"command": "ls"},
                "reason": "Verify the directory was created."
            }
        ]
    })

    with patch('backend.llm_client.get_llm_response', new_callable=AsyncMock, return_value=mock_plan_json_string):
        with patch('backend.memory_manager.memory_manager.retrieve_from_memory', return_value=[]):
            with patch('backend.tools.get_tool_definitions', return_value=[]):
                with patch('backend.utils.parse_json_from_response', return_value=json.loads(mock_plan_json_string)):
                    with patch('backend.utils.plan_sanity_check', return_value=(True, "")):
                        with patch('backend.utils.validate_plan_semantically', new_callable=AsyncMock, return_value=(True, "Test approval", json.loads(mock_plan_json_string)['plan'])):
                            with patch('backend.tools.execute_tool', new_callable=AsyncMock, return_value={"status": "success", "data": "Directory created."}):
                                result = await run_agent(user_prompt, session_id, chat_history)

                                assert result['response'] == "Directory created."

@pytest.mark.asyncio
async def test_run_agent_plan_generation_failure():
    user_prompt = "Create a new directory called 'my_test_project'."
    session_id = "test-session-id"
    chat_history = []

    mock_invalid_plan_json_string = json.dumps({"invalid_key": "invalid_value"})

    with patch('backend.llm_client.get_llm_response', new_callable=AsyncMock, return_value=mock_invalid_plan_json_string):
        with patch('backend.memory_manager.memory_manager.retrieve_from_memory', return_value=[]):
            with patch('backend.tools.get_tool_definitions', return_value=[]):
                with patch('backend.utils.parse_json_from_response', return_value=json.loads(mock_invalid_plan_json_string)):
                    result = await run_agent(user_prompt, session_id, chat_history)

                    assert "Invalid plan structure" in result['response']

@pytest.mark.asyncio
async def test_run_agent_execution_failure():
    user_prompt = "Create a new directory called 'my_test_project'."
    session_id = "test-session-id"
    chat_history = []

    mock_plan_json_string = json.dumps({
        "plan": [
            {
                "tool": {"name": "execute_script"},
                "parameters": {"command": "mkdir my_test_project"},
                "reason": "Create a new directory for the Python project."
            }
        ]
    })

    with patch('backend.llm_client.get_llm_response', new_callable=AsyncMock, return_value=mock_plan_json_string):
        with patch('backend.memory_manager.memory_manager.retrieve_from_memory', return_value=[]):
            with patch('backend.tools.get_tool_definitions', return_value=[]):
                with patch('backend.utils.parse_json_from_response', return_value=json.loads(mock_plan_json_string)):
                    with patch('backend.utils.plan_sanity_check', return_value=(True, "")):
                        with patch('backend.utils.validate_plan_semantically', new_callable=AsyncMock, return_value=(True, "Test approval", json.loads(mock_plan_json_string)['plan'])):
                            with patch('backend.tools.execute_tool', new_callable=AsyncMock, return_value={"status": "error", "message": "Command not found"}):
                                result = await run_agent(user_prompt, session_id, chat_history)

                                assert "Command not found" in result['response']

@pytest.mark.asyncio
async def test_run_agent_max_retries_exceeded():
    user_prompt = "Create a new directory called 'my_test_project'."
    session_id = "test-session-id"
    chat_history = []

    mock_plan_json_string = json.dumps({
        "plan": [
            {
                "tool": {"name": "execute_script"},
                "parameters": {"command": "mkdir my_test_project"},
                "reason": "Create a new directory for the Python project."
            }
        ]
    })

    with patch('backend.llm_client.get_llm_response', new_callable=AsyncMock, return_value=mock_plan_json_string):
        with patch('backend.memory_manager.memory_manager.retrieve_from_memory', return_value=[]):
            with patch('backend.tools.get_tool_definitions', return_value=[]):
                with patch('backend.utils.parse_json_from_response', return_value=json.loads(mock_plan_json_string)):
                    with patch('backend.utils.plan_sanity_check', return_value=(True, "")):
                        with patch('backend.utils.validate_plan_semantically', new_callable=AsyncMock, return_value=(True, "Test approval", json.loads(mock_plan_json_string)['plan'])):
                            with patch('backend.tools.execute_tool', new_callable=AsyncMock, return_value={"status": "error", "message": "Command not found"}):
                                result = await run_agent(user_prompt, session_id, chat_history)

                                assert "Agent failed after 1 attempts. Last error: Execution stopped at step 1" in result['response']


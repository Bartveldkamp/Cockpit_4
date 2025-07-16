# tests/test_lucidus.py

import pytest
from backend.lucidus.verification import verify_code

@pytest.mark.asyncio
async def test_verify_code():
    code_snippet = "def hello_world():\n    print('Hello, World!')"
    result = await verify_code(code_snippet)

    # Check if the result is a dictionary
    assert isinstance(result, dict)

    # Check for the expected keys in the result
    assert "complexity" in result
    assert "confidence" in result
    assert "evidence" in result
    assert "reasoning" in result

    # Additional checks based on expected values
    assert isinstance(result["complexity"], str)
    assert isinstance(result["confidence"], (int, float))
    assert isinstance(result["evidence"], list)
    assert isinstance(result["reasoning"], str)

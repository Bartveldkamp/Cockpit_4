import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock
from backend.lucidus.api import router

client = TestClient(router)

@pytest.mark.asyncio
async def test_lucidus_verify_endpoint_success():
    code_data = {
        "code_snippet": "print('Hello, world!')",
        "context": "Test context"
    }

    expected_response = {
        "complexity": "low",
        "confidence": 0.95,
        "verdict": "safe",
        "reasoning": "The code is safe.",
        "evidence": [{"detail": "No issues found"}]
    }

    with patch('backend.lucidus.api.verify_code', new_callable=AsyncMock) as mock_verify_code:
        mock_verify_code.return_value = expected_response

        response = client.post("/lucidus_verify", json=code_data)

        assert response.status_code == 200
        assert response.json() == expected_response

@pytest.mark.asyncio
async def test_lucidus_verify_endpoint_missing_code_snippet():
    code_data = {
        "context": "Test context"
    }

    response = client.post("/lucidus_verify", json=code_data)

    assert response.status_code == 400
    assert response.json() == {"detail": "'code_snippet' is required for Lucidus verification."}

@pytest.mark.asyncio
async def test_lucidus_verify_endpoint_exception():
    code_data = {
        "code_snippet": "print('Hello, world!')",
        "context": "Test context"
    }

    with patch('backend.lucidus.api.verify_code', new_callable=AsyncMock) as mock_verify_code:
        mock_verify_code.side_effect = Exception("Verification failed")

        with patch('backend.lucidus.api.logger.error') as mock_logger_error:
            response = client.post("/lucidus_verify", json=code_data)

            assert response.status_code == 500
            assert response.json() == {"detail": "Error during Lucidus verification: Verification failed"}
            mock_logger_error.assert_called_once_with("Error during Lucidus verification: Verification failed")

            assert response.json() == {"detail": "Error during Lucidus verification: Verification failed"}
            mock_logger_error.assert_called_once_with("Error during Lucidus verification: Verification failed")

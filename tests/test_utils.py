import pytest
import asyncio
from unittest.mock import patch, AsyncMock
from backend.utils import retry_with_backoff, SecurityDecision

@pytest.mark.asyncio
async def test_retry_with_backoff_success_first_attempt():
    @retry_with_backoff(max_retries=3)
    async def successful_function():
        return "success"

    result = await successful_function()
    assert result == "success"

@pytest.mark.asyncio
async def test_retry_with_backoff_success_after_retries():
    @retry_with_backoff(max_retries=3)
    async def flaky_function(attempts):
        nonlocal attempt_count
        attempt_count += 1
        if attempt_count < attempts:
            raise Exception("Temporary failure")
        return "success"

    attempt_count = 0
    result = await flaky_function(attempts=2)
    assert result == "success"
    assert attempt_count == 2

@pytest.mark.asyncio
async def test_retry_with_backoff_exhaust_retries():
    @retry_with_backoff(max_retries=2)
    async def always_failing_function():
        raise Exception("Always fails")

    with pytest.raises(Exception, match="Always fails"):
        await always_failing_function()

@pytest.mark.asyncio
async def test_retry_with_backoff_logging():
    @retry_with_backoff(max_retries=2)
    async def failing_function():
        raise Exception("Temporary failure")

    with patch('backend.utils.logger.warning') as mock_warning:
        with pytest.raises(Exception, match="Temporary failure"):
            await failing_function()

        assert mock_warning.call_count == 2

@pytest.mark.asyncio
async def test_retry_with_backoff_backoff_delay():
    @retry_with_backoff(max_retries=2, base_delay=1.0, max_delay=10.0)
    async def failing_function():
        raise Exception("Temporary failure")

    with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
        with pytest.raises(Exception, match="Temporary failure"):
            await failing_function()

        # Ensure sleep is called with the correct delays
        assert mock_sleep.call_count == 2
        assert mock_sleep.await_args_list[0][0][0] <= 2.0  # First retry delay should be <= 2.0
        assert mock_sleep.await_args_list[1][0][0] <= 4.0  # Second retry delay should be <= 4.0

def test_security_decision():
    decision = SecurityDecision(is_safe=True, reasoning="Safe command")
    assert decision.is_safe is True
    assert decision.reasoning == "Safe command"

    decision = SecurityDecision(is_safe=False, reasoning="Unsafe command")
    assert decision.is_safe is False
    assert decision.reasoning == "Unsafe command"

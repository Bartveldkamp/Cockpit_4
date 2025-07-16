import pytest
import httpx
from unittest.mock import patch, AsyncMock
from backend.llm_client import get_llm_response, _count_tokens, _print_metrics

# Test for _count_tokens function
def test_count_tokens():
    text = "Hello, world!"
    expected_token_count = 4  # This is an example, adjust based on actual tokenizer behavior
    assert _count_tokens(text) == expected_token_count

def test_count_tokens_no_tokenizer():
    with patch('backend.llm_client.tokenizer', None):
        text = "Hello, world!"
        assert _count_tokens(text) == 0

# Test for _print_metrics function
def test_print_metrics(capsys):
    model = "model1"
    input_tokens = 1000
    output_tokens = 500
    _print_metrics(model, input_tokens, output_tokens)
    captured = capsys.readouterr()
    assert "Model: model1" in captured.out
    assert "Input Tokens: 1000" in captured.out
    assert "Output Tokens: 500" in captured.out
    assert "Estimated Cost: \$0.015000" in captured.out

# Test for get_llm_response function
@pytest.mark.asyncio
async def test_get_llm_response_success():
    provider = "mistral"
    model_name = "model1"
    messages = [{"role": "user", "content": "Hello, world!"}]
    temperature = 0.7

    mock_response = {
        "choices": [{"message": {"content": "Hi there!"}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5}
    }

    with patch('backend.llm_client.settings.mistral_api_key', 'test_api_key'):
        with patch('backend.llm_client.settings.mistral_api_url', 'https://api.mistral.ai/v1/chat/completions'):
            with patch('httpx.AsyncClient.post', new_callable=AsyncMock) as mock_post:
                mock_post.return_value.json.return_value = mock_response
                mock_post.return_value.raise_for_status = AsyncMock()

                response = await get_llm_response(provider, model_name, messages, temperature)

                assert response == "Hi there!"

@pytest.mark.asyncio
async def test_get_llm_response_timeout():
    provider = "mistral"
    model_name = "model1"
    messages = [{"role": "user", "content": "Hello, world!"}]
    temperature = 0.7

    with patch('backend.llm_client.settings.mistral_api_key', 'test_api_key'):
        with patch('backend.llm_client.settings.mistral_api_url', 'https://api.mistral.ai/v1/chat/completions'):
            with patch('httpx.AsyncClient.post', new_callable=AsyncMock) as mock_post:
                mock_post.side_effect = httpx.ReadTimeout("Request timed out")

                response = await get_llm_response(provider, model_name, messages, temperature)

                assert response == "API_ERROR: The request to the AI model timed out. The task may be too complex."

@pytest.mark.asyncio
async def test_get_llm_response_http_error():
    provider = "mistral"
    model_name = "model1"
    messages = [{"role": "user", "content": "Hello, world!"}]
    temperature = 0.7

    with patch('backend.llm_client.settings.mistral_api_key', 'test_api_key'):
        with patch('backend.llm_client.settings.mistral_api_url', 'https://api.mistral.ai/v1/chat/completions'):
            with patch('httpx.AsyncClient.post', new_callable=AsyncMock) as mock_post:
                mock_post.side_effect = httpx.HTTPStatusError(
                    message="HTTP error", request=httpx.Request('POST', 'https://api.mistral.ai/v1/chat/completions'),
                    response=httpx.Response(400, text="Bad Request")
                )

                response = await get_llm_response(provider, model_name, messages, temperature)

                assert response == "API_ERROR: HTTP 400 - Bad Request"

@pytest.mark.asyncio
async def test_get_llm_response_unexpected_error():
    provider = "mistral"
    model_name = "model1"
    messages = [{"role": "user", "content": "Hello, world!"}]
    temperature = 0.7

    with patch('backend.llm_client.settings.mistral_api_key', 'test_api_key'):
        with patch('backend.llm_client.settings.mistral_api_url', 'https://api.mistral.ai/v1/chat/completions'):
            with patch('httpx.AsyncClient.post', new_callable=AsyncMock) as mock_post:
                mock_post.side_effect = Exception("Unexpected error")

                response = await get_llm_response(provider, model_name, messages, temperature)

                assert response == "APP_ERROR: Unexpected error"

@pytest.mark.asyncio
async def test_get_llm_response_missing_api_key():
    provider = "mistral"
    model_name = "model1"
    messages = [{"role": "user", "content": "Hello, world!"}]
    temperature = 0.7

    with patch('backend.llm_client.settings.mistral_api_key', ''):
        response = await get_llm_response(provider, model_name, messages, temperature)

        assert response == "API_ERROR: MISTRAL_API_KEY environment variable not set."

@pytest.mark.asyncio
async def test_get_llm_response_unsupported_provider():
    provider = "unsupported"
    model_name = "model1"
    messages = [{"role": "user", "content": "Hello, world!"}]
    temperature = 0.7

    with pytest.raises(NotImplementedError):
        await get_llm_response(provider, model_name, messages, temperature)

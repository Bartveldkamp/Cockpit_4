import os
import httpx
import logging
import tiktoken
from typing import List, Dict, Any, Optional

from backend.config import settings

# --- Initialization ---
logger = logging.getLogger(__name__)
try:
    tokenizer = tiktoken.get_encoding("cl100k_base")
except Exception:
    logger.warning("Could not initialize tiktoken, token counts will be unavailable.")
    tokenizer = None

# --- Helper Functions ---
def _count_tokens(text: str) -> int:
    if not tokenizer or not isinstance(text, str):
        return 0
    return len(tokenizer.encode(text))

# Define MODEL_PRICES
MODEL_PRICES = {
    "model1": {"input": 0.01, "output": 0.02},
    "model2": {"input": 0.015, "output": 0.025},
    # Add other models and their prices here
}

def _print_metrics(model: str, input_tokens: int, output_tokens: int):
    prices = MODEL_PRICES.get(model)
    cost_str = "N/A"
    if prices:
        input_cost = (input_tokens / 1_000_000) * prices["input"]
        output_cost = (output_tokens / 1_000_000) * prices["output"]
        total_cost = input_cost + output_cost
        cost_str = f"${total_cost:.6f}"
    metrics_str = (
        "\n=================================================="
        f"\n📊 LLM Call Metrics:"
        f"\n   - Model: {model}"
        f"\n   - Input Tokens: {input_tokens}"
        f"\n   - Output Tokens: {output_tokens}"
        f"\n   - Estimated Cost: {cost_str}"
        "\n=================================================="
    )
    print(metrics_str)

# --- Core Function ---
async def get_llm_response(
    provider: str, model_name: str, messages: List[Dict[str, Any]],
    temperature: float, top_p: Optional[float] = 1.0, max_tokens: Optional[int] = 4096,
    stop_tokens: Optional[List[str]] = None,
) -> str:
    if provider.lower() != "mistral":
        raise NotImplementedError("Currently, only the 'mistral' provider is supported.")

    if not settings.mistral_api_key:
        return "API_ERROR: MISTRAL_API_KEY environment variable not set."

    headers = {"Authorization": f"Bearer {settings.mistral_api_key}", "Content-Type": "application/json"}
    payload = {
        "model": model_name, "messages": messages, "temperature": temperature,
        "top_p": top_p, "max_tokens": max_tokens, "stop": stop_tokens or [],
    }
    payload = {k: v for k, v in payload.items() if v is not None}

    try:
        # Increased timeout to 300 seconds (5 minutes) for complex tasks.
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(settings.mistral_api_url, headers=headers, json=payload)
            response.raise_for_status()

            data = response.json()
            response_content = data["choices"][0]["message"]["content"]

            input_tokens = data.get("usage", {}).get("prompt_tokens", 0)
            output_tokens = data.get("usage", {}).get("completion_tokens", 0)
            _print_metrics(model_name, input_tokens, output_tokens)

            return response_content

    except httpx.ReadTimeout:
        logger.error(f"Request to LLM API timed out.")
        return "API_ERROR: The request to the AI model timed out. The task may be too complex."
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error calling LLM API: {e.response.status_code} - {e.response.text}")
        return f"API_ERROR: HTTP {e.response.status_code} - {e.response.text}"
    except Exception as e:
        logger.error(f"An unexpected error occurred in get_llm_response: {e}", exc_info=True)
        return f"APP_ERROR: {str(e)}"

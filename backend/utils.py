# backend/utils.py
import asyncio
import json
import logging
import random
import re
from functools import wraps
from typing import Any, Dict, List, NamedTuple

from pydantic import ValidationError

from backend.config import settings
from backend.llm_client import get_llm_response
from backend.schemas import PlanModel, StepModel


logger = logging.getLogger(__name__)

class SecurityDecision(NamedTuple):
    is_safe: bool
    reasoning: str

def retry_with_backoff(max_retries: int, base_delay: float = 1.0, max_delay: float = 10.0):
    """Decorator to retry an async function with exponential backoff and jitter."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    if attempt >= max_retries:
                        logger.error(
                            f"[{func.__name__}] Failed after {attempt} attempts: {e}"
                        )
                        raise
                    
                    exp_delay = base_delay * (2 ** attempt)
                    delay = min(exp_delay, max_delay)
                    jitter = random.uniform(0, delay / 4)
                    
                    logger.warning(
                        f"[{func.__name__}] Attempt {attempt+1}/{max_retries+1} failed "
                        f"with error: {e!r}. Retrying in {delay + jitter:.2f}s."
                    )
                    await asyncio.sleep(delay + jitter)
        return wrapper
    return decorator

def parse_json_from_response(response_str: str) -> Any:
    """Finds the first '{' and the last '}' and parses everything in between."""
    try:
        first_brace = response_str.find('{')
        last_brace = response_str.rfind('}')
        if first_brace != -1 and last_brace != -1:
            json_str = response_str[first_brace:last_brace+1]
            return json.loads(json_str)
        else:
            return {"content": response_str}
    except (json.JSONDecodeError, TypeError):
        return {"content": response_str}

def substitute_placeholders(parameters: Dict[str, Any], results: Dict[int, Any]) -> Dict[str, Any]:
    """Substitutes placeholders like <ref:step_1_result> in a tool's parameter dictionary."""
    if not isinstance(parameters, dict):
        return parameters
    output_params = parameters.copy()
    for key, value in output_params.items():
        if isinstance(value, str):
            placeholder_pattern = r"<ref:step_(\d+)_result>|{{\s*step_(\d+)_result\s*}}"
            def replace_match(match):
                step_index_str = match.group(1) or match.group(2)
                step_index = int(step_index_str)
                if step_index in results:
                    return str(results[step_index].get("data", ""))
                return match.group(0)
            output_params[key] = re.sub(placeholder_pattern, replace_match, value)
    return output_params

def plan_sanity_check(plan: List[StepModel], user_prompt: str) -> (bool, str):
    """Verifies that filenames used in the plan were not hallucinated."""
    prompt_filenames = set(re.findall(r'[`"]?([\w\.\-\_\/]+?\.(?:py|json|txt|md|sh|yaml|yml))[`"]?', user_prompt))
    if not prompt_filenames:
        return True, ""
    for step in plan:
        if step.parameters and "filename" in step.parameters:
            plan_filename = step.parameters["filename"]
            if plan_filename not in prompt_filenames:
                error_msg = f"Plan validation failed: Agent hallucinated filename '{plan_filename}'."
                logger.error(error_msg)
                return False, error_msg
    return True, ""

async def validate_plan_semantically(plan_list: List[Dict[str, Any]], user_prompt: str, correlation_id: str) -> (bool, str, List[Dict[str, Any]]):
    """Uses an LLM to check if a plan is logically sound."""
    logger.info("Engaging Plan Critic for semantic validation.")
    critic_system_prompt = "You are a 'Plan Critic' AI. Evaluate the provided JSON plan based on the user's goal for logic and efficiency. If the plan is sound, respond ONLY with the word OK. If it is flawed, respond ONLY with a corrected, complete, and valid JSON plan object."
    plan_str = json.dumps({"plan": plan_list}, indent=2)
    critic_user_prompt = f"User Goal: \"{user_prompt}\"\n\nGenerated Plan:\n{plan_str}"
    messages = [{"role": "system", "content": critic_system_prompt}, {"role": "user", "content": critic_user_prompt}]

    response_str = await get_llm_response(
        provider="mistral", model_name=settings.mistral_model, messages=messages, temperature=0.0
    )
    if response_str.strip().upper() == "OK":
        logger.info("Plan Critic approved the plan.")
        return True, "Plan is logically sound.", plan_list
    else:
        logger.warning("Plan Critic detected a flaw and provided a correction.")
        try:
            corrected_plan_data = parse_json_from_response(response_str)
            if "plan" in corrected_plan_data:
                PlanModel(**corrected_plan_data) # Validate the corrected plan
                return True, "Plan was corrected by Critic.", corrected_plan_data['plan']
            else: 
                return False, "Critic provided an invalid correction format.", plan_list
        except (ValidationError, json.JSONDecodeError) as e:
            logger.error(f"Critic's corrected plan was invalid: {e}")
            return False, f"Critic's corrected plan was invalid: {e}", plan_list

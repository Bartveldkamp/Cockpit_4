import json
import logging
from typing import Any, Dict, List

from backend.config import settings
from backend.memory import memory_manager
from backend.llm_client import get_llm_response
from backend.schemas import PlanModel
from backend.tools import get_tool_definitions, execute_tool, substitute_placeholders
from backend.utils import parse_json_from_response, plan_sanity_check, validate_plan_semantically

logger = logging.getLogger(__name__)

async def run_agent(
    user_prompt: str, session_id: str, chat_history: list, correlation_id: str = "no-correlation-id"
) -> Dict[str, Any]:
    logger.info(f"Execution Agent starting task: '{user_prompt[:100]}...'")
    original_user_prompt = user_prompt
    full_history = list(chat_history)
    full_history.append({"role": "user", "content": original_user_prompt})
    max_retries = settings.max_retries
    execution_error = None

    for attempt in range(max_retries):
        if attempt > 0:
            user_prompt = (
                f"My original goal was: '{original_user_prompt}'.\n\n"
                f"My last plan failed with the following error:\n{execution_error}\n\n"
                "Please analyze the error and create a new, corrected plan to achieve my original goal. Do not repeat the mistake."
            )

        print("\n--- STAGE 0: MEMORY RETRIEVAL ---")
        retrieved_context_list = memory_manager.retrieve_from_memory(user_prompt)
        context_str = "\n\n---\n\n".join(retrieved_context_list)
        if context_str:
            logger.info("Injecting retrieved context.")
        else:
            logger.info("No relevant context found in memory.")

        print(f"\n--- STAGE 1: PLAN GENERATION (Attempt {attempt + 1}/{max_retries}) ---")
        tool_schemas_str = json.dumps(get_tool_definitions(), indent=2)

        planning_system_prompt = (
            "You are a tactical AI agent. Your only job is to take a single, simple, concrete task and create a JSON plan to execute it using the available tools. "
            "Your output MUST be a JSON object with a 'plan' key.\n\n"
            "**CRITICAL RESPONSE FORMATTING:**\n"
            "1. Your output MUST be a single JSON object with a single root key named \"plan\".\n"
            "2. The value of \"plan\" MUST be a list of step objects.\n"
            "3. Each step object in the list MUST have EXACTLY three keys: \"tool\", \"parameters\", and \"reason\".\n"
            "4. **Each step must represent a single, atomic action.** Do NOT combine multiple commands into one step.\n"
            "5. The \"parameters\" for the \"execute_script\" tool must contain a single key named \"command\" whose value is a string.\n\n"
            "Example of a PERFECT response:\n"
            "{\n"
            '  "plan": [\n'
            '    {\n'
            '      "tool": {"name": "execute_script"},\n'
            '      "parameters": {"command": "echo \'hello world\'"},\n'
            '      "reason": "This is an example step to print hello world."\n'
            '    }\n'
            '  ]\n'
            '}\n\n'
            "### CONTEXT FROM LONG-TERM MEMORY ###\n"
            f"{context_str if context_str else 'No relevant context found.'}\n"
            "### END CONTEXT ###\n\n"
            "AVAILABLE TOOLS:\n"
            f"{tool_schemas_str}\n\n"
            "Now, create a plan for the user's simple request."
        )

        planning_messages = [{"role": "system", "content": planning_system_prompt}, {"role": "user", "content": user_prompt}]

        llm_plan_response_str = await get_llm_response(
            provider="mistral", model_name=settings.mistral_model, messages=planning_messages,
            temperature=0.0, top_p=1.0, max_tokens=4096
        )
        parsed_data = parse_json_from_response(llm_plan_response_str)
        print("--- RAW LLM JSON ---")
        print(parsed_data)
        if "content" in parsed_data:
            return {"response": parsed_data["content"], "full_history": full_history}

        try:
            plan = PlanModel(**parsed_data).plan
        except ValidationError:
            try:
                plan = PlanModel(plan=parsed_data).plan
            except ValidationError as e:
                logger.error(f"Pydantic validation failed on both attempts: {e}")
                return {"response": f"Invalid plan structure: {e}", "full_history": full_history}

        is_sane, sanity_error = plan_sanity_check(plan, user_prompt)
        if not is_sane:
            return {"response": sanity_error, "full_history": full_history}

        is_logical, comment, corrected_plan_list = await validate_plan_semantically(parsed_data['plan'], user_prompt, correlation_id)
        if not is_logical:
            return {"response": f"Semantic validation failed: {comment}", "full_history": full_history}

        plan = PlanModel(plan=corrected_plan_list).plan
        logger.info(f"Plan semantic validation: SUCCESS. {comment}")
        full_history.append({"role": "assistant", "content": f"Plan Generated (and validated): {comment}\n```json\n{json.dumps({'plan': corrected_plan_list}, indent=2)}\n```"})
        print(f"✅ Plan generated with {len(plan)} steps.")

        print("\n--- STAGE 2: EXECUTION ---")
        step_results = {}
        execution_error = None

        for i, step in enumerate(plan):
            print(f"Executing step {i+1}/{len(plan)}: {step.tool}")
            params = substitute_placeholders(step.parameters, step_results)
            tool_output = await execute_tool(step.tool, params, session_id, original_user_prompt)
            step_results[i] = tool_output
            print(f"🔭 Observed: {tool_output}")
            if tool_output.get("status") == "error":
                error_message = f"Execution stopped at step {i+1} ({step.tool}): {tool_output.get('message')}"
                full_history.append({"role": "assistant", "content": error_message})
                retryable_errors = ["not found", "does not exist"]
                is_retryable = any(keyword in error_message.lower() for keyword in retryable_errors)
                if is_retryable:
                    execution_error = error_message
                    break
                else:
                    logger.error(f"Execution failed with a non-retryable error. Halting.")
                    return {"response": error_message, "full_history": full_history}

        if not execution_error:
            print("\n--- STAGE 3: FINAL REPORT ---")
            final_result = step_results.get(len(plan) - 1, {})
            final_answer = final_result.get("data", "The plan has been executed successfully.")
            full_history.append({"role": "assistant", "content": str(final_answer)})
            return {"response": str(final_answer), "full_history": full_history}

    final_error_message = f"Agent failed after {max_retries} attempts. Last error: {execution_error}"
    full_history.append({"role": "assistant", "content": final_error_message})
    return {"response": final_error_message, "full_history": full_history}

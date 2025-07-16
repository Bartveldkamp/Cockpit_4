import os
import json
import logging
import subprocess
import asyncio
from typing import Any, Dict, List, NamedTuple
import git
from pathlib import Path

from backend.llm_client import get_llm_response
from backend.vault import VAULT_ROOT
from backend.memory_manager import memory_manager
from backend.config import settings
from backend.schemas import ToolModel
from backend.utils import retry_with_backoff, SecurityDecision

logger = logging.getLogger(__name__)

async def assess_command(command: str, user_prompt: str) -> SecurityDecision:
    safe_commands = ["ls", "cat", "pwd", "pip list", "echo"]
    if any(command.strip().startswith(safe_cmd) for safe_cmd in safe_commands):
        logger.info(f"Command '{command}' passed pre-filter as safe.")
        return SecurityDecision(is_safe=True, reasoning="Command passed pre-filter as safe.")

    logger.info(f"Engaging AI Security Officer to assess command: '{command}'")

    security_prompt = (
        "You are an AI Security Officer. Your only job is to determine if a shell command is safe to execute in the context of a user's request. "
        "The command is considered 'SAFE' if it is not destructive (e.g., no `rm -rf`, `mv` on important files, `dd`), is not trying to access sensitive system files outside its workspace, and is directly related to the user's goal. "
        "The command is 'UNSAFE' if it is destructive, tries to escalate privileges (`sudo`), or is clearly unrelated to the goal.\n\n"
        f"User's Goal: \"{user_prompt}\"\n"
        f"Command to Assess: \"{command}\"\n\n"
        "Is this command SAFE or UNSAFE? Respond with ONLY the word SAFE or UNSAFE, followed by the reasoning."
    )

    messages = [{"role": "system", "content": security_prompt}]

    response = await get_llm_response(
        provider="mistral", model_name=settings.mistral_model, messages=messages,
        temperature=0.0, max_tokens=50
    )

    parts = response.strip().split(None, 1)
    label = parts[0].upper()
    reasoning = parts[1] if len(parts) > 1 else ""
    is_safe = label == "SAFE"

    if is_safe:
        logger.info(f"Security Officer approved command: '{command}'")
    else:
        logger.warning(f"Security Officer REJECTED command: '{command}'")

    return SecurityDecision(is_safe=is_safe, reasoning=reasoning)

def get_tool_definitions() -> List[Dict[str, Any]]:
    return [
        {
            "name": "final_answer",
            "description": "Provides a direct, final answer to the user's question.",
            "parameters": { "type": "object", "properties": {"answer": {"type": "string"}}, "required": ["answer"] },
        },
        {
            "name": "execute_script",
            "description": "Executes a single shell command.",
            "parameters": { "type": "object", "properties": {"command": {"type": "string"}, "working_dir": {"type": "string"}}, "required": ["command"] },
        },
        {
            "name": "git_clone",
            "description": "Clones a remote Git repository.",
            "parameters": { "type": "object", "properties": {"repo_url": {"type": "string"}, "local_path": {"type": "string"}}, "required": ["repo_url"] },
        },
        {
            "name": "git_commit_and_push",
            "description": "Stages all changes, commits, and pushes to the 'main' branch.",
            "parameters": { "type": "object", "properties": {"repo_path": {"type": "string"}, "commit_message": {"type": "string"}}, "required": ["repo_path", "commit_message"] },
        },
        {
            "name": "code_generation",
            "description": "Generates Python code.",
            "parameters": { "type": "object", "properties": {"prompt": {"type": "string"}}, "required": ["prompt"] },
        },
        {
            "name": "write_file",
            "description": "Writes content to a file.",
            "parameters": { "type": "object", "properties": {"filename": {"type": "string"}, "content": {"type": "string"}}, "required": ["filename", "content"] },
        },
        {
            "name": "read_file",
            "description": "Reads the content of a file.",
            "parameters": { "type": "object", "properties": {"filename": {"type": "string"}}, "required": ["filename"] },
        },
        {
            "name": "list_files",
            "description": "Lists all files in the session.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
        {
            "name": "refactor_code",
            "description": "Reads a file, asks an LLM to refactor it based on a prompt, and writes the result back to the file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "The path to the file to be refactored."},
                    "refactoring_prompt": {"type": "string", "description": "A clear instruction on how the code should be refactored."}
                },
                "required": ["filename", "refactoring_prompt"]
            },
        },
    ]

async def handle_final_answer(params: Dict[str, Any], **kwargs) -> Dict[str, Any]:
    answer = params.get("answer", "I have processed the request.")
    return {"status": "success", "data": answer}

def run_in_user_namespace(command: str, cwd: str) -> Dict[str, Any]:
    result = subprocess.run(
        ["unshare", "-U", "-r", "-m", "--", "sh", "-c", command],
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    return {
        "status": "success" if result.returncode == 0 else "error",
        "output": result.stdout if result.returncode == 0 else result.stderr,
        "exit_code": result.returncode
    }

@retry_with_backoff(max_retries=3, base_delay=2.0, max_delay=10.0)
async def handle_execute_script(params: Dict[str, Any], session_id: str, user_prompt: str, **kwargs) -> Dict[str, Any]:
    command = params.get("command")
    if not command or not command.strip():
        return {"status": "error", "message": "Missing or invalid 'command' parameter."}

    session_vault_path = Path(VAULT_ROOT) / session_id
    working_dir_name = params.get("working_dir", ".")
    target_cwd = (session_vault_path / working_dir_name).resolve()
    if not target_cwd.is_relative_to(session_vault_path):
        return {"status": "error", "message": "Directory traversal is not allowed."}
    if not target_cwd.is_dir():
        return {"status": "error", "message": f"Working directory '{working_dir_name}' does not exist."}

    risk_assessment = await assess_command(command, user_prompt)
    if not risk_assessment.is_safe:
        return {"status": "error", "message": f"Execution of command '{command}' was denied by AI Security Officer. Reason: {risk_assessment.reasoning}"}

    logger.info(f"Executing AI-approved shell command: '{command}' in '{target_cwd}'", extra={"session_id": session_id, "command": command, "tool": "execute_script"})

    result = run_in_user_namespace(command, str(target_cwd))

    if result["status"] == "success":
        return {"status": "success", "data": result["output"]}
    else:
        return {"status": "error", "message": result["output"], "exit_code": result["exit_code"]}

@retry_with_backoff(max_retries=3, base_delay=2.0, max_delay=10.0)
async def handle_git_clone(params: Dict[str, Any], session_id: str, **kwargs) -> Dict[str, Any]:
    repo_url = params.get("repo_url")
    if not repo_url:
        return {"status": "error", "message": "Missing 'repo_url' parameter."}
    repo_name = repo_url.split('/')[-1].replace('.git', '')
    local_path = params.get("local_path", repo_name)
    session_vault_path = Path(VAULT_ROOT) / session_id
    clone_path = session_vault_path / local_path
    if clone_path.exists():
        return {"status": "error", "message": f"Directory '{local_path}' already exists."}
    logger.info(f"Cloning repository from '{repo_url}' into '{clone_path}'...", extra={"session_id": session_id, "tool": "git_clone", "repo_url": repo_url})
    git.Repo.clone_from(repo_url, str(clone_path))
    return {"status": "success", "data": f"Successfully cloned repository into '{local_path}'."}

@retry_with_backoff(max_retries=3, base_delay=2.0, max_delay=10.0)
async def handle_git_commit_and_push(params: Dict[str, Any], session_id: str, **kwargs) -> Dict[str, Any]:
    repo_path = params.get("repo_path")
    commit_message = params.get("commit_message")
    if not repo_path or not commit_message:
        return {"status": "error", "message": "Missing 'repo_path' or 'commit_message'."}
    session_vault_path = Path(VAULT_ROOT) / session_id
    full_repo_path = session_vault_path / repo_path
    if not full_repo_path.is_dir():
        return {"status": "error", "message": f"Repository path '{repo_path}' does not exist."}
    logger.info(f"Committing and pushing changes in '{full_repo_path}'...", extra={"session_id": session_id, "tool": "git_commit_and_push", "repo_path": repo_path})
    repo = git.Repo(str(full_repo_path))
    repo.git.add(A=True)
    if not repo.is_dirty(untracked_files=True):
        return {"status": "success", "data": "No changes to commit."}
    repo.index.commit(commit_message)
    origin = repo.remote(name='origin')
    push_info = origin.push()
    if any(p.flags & git.PushInfo.ERROR for p in push_info):
        error_summary = "\n".join([str(p.summary) for p in push_info if p.flags & git.PushInfo.ERROR])
        return {"status": "error", "message": f"Failed to push to remote: {error_summary}"}
    return {"status": "success", "data": f"Successfully committed and pushed changes with message: '{commit_message}'."}

@retry_with_backoff(max_retries=5, base_delay=5.0, max_delay=30.0)
async def handle_code_generation(params: Dict[str, Any], **kwargs) -> Dict[str, Any]:
    prompt = params.get("prompt")
    if not prompt:
        return {"status": "error", "message": "Missing 'prompt'."}
    code_gen_system_prompt = "You are a code generation engine..."
    code_string = await get_llm_response(
        provider="mistral", model_name="codestral-latest",
        messages=[{"role": "system", "content": code_gen_system_prompt}, {"role": "user", "content": prompt}],
        temperature=0.0, top_p=1.0, max_tokens=4096, stop_tokens=[]
    )
    return {"status": "success", "data": code_string}

async def handle_write_file(params: Dict[str, Any], session_id: str, **kwargs) -> Dict[str, Any]:
    filename = params.get("filename")
    content = params.get("content", "")
    if not filename:
        return {"status": "error", "message": "Missing 'filename'."}
    session_vault_path = Path(VAULT_ROOT) / session_id
    file_path = session_vault_path / filename
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open('w', encoding='utf-8') as f:
        f.write(content)
    memory_manager.add_to_memory(content=content, filename=filename, session_id=session_id)
    return {"status": "success", "data": f"Successfully wrote {len(content.encode('utf-8'))} bytes to '{filename}'."}

async def handle_read_file(params: Dict[str, Any], session_id: str, **kwargs) -> Dict[str, Any]:
    filename = params.get("filename")
    if not filename:
        return {"status": "error", "message": "Missing 'filename'."}
    session_vault_path = Path(VAULT_ROOT) / session_id
    project_root_path = Path(VAULT_ROOT).resolve().parent
    session_file_path = session_vault_path / filename
    root_file_path = project_root_path / filename
    if session_file_path.exists():
        file_path_to_read = session_file_path
    elif root_file_path.exists():
        file_path_to_read = root_file_path
    else:
        return {"status": "error", "message": f"File '{filename}' not found in session vault or project root."}
    with file_path_to_read.open('r', encoding='utf-8') as f:
        content = f.read()
    return {"status": "success", "data": content}

async def handle_list_files(params: Dict[str, Any], session_id: str, **kwargs) -> Dict[str, Any]:
    session_vault_path = Path(VAULT_ROOT) / session_id
    if not session_vault_path.exists():
        return {"status": "success", "data": "No files in session."}
    files = [f.name for f in session_vault_path.iterdir() if f.is_file()]
    if not files:
        return {"status": "success", "data": "No files in session."}
    return {"status": "success", "data": "\n".join(files)}

async def handle_refactor_code(params: Dict[str, Any], session_id: str, **kwargs) -> Dict[str, Any]:
    filename = params.get("filename")
    refactoring_prompt = params.get("refactoring_prompt")

    if not filename or not refactoring_prompt:
        return {"status": "error", "message": "Missing 'filename' or 'refactoring_prompt'."}

    read_result = await handle_read_file({"filename": filename}, session_id=session_id)
    if read_result["status"] == "error":
        return read_result

    original_code = read_result["data"]

    full_prompt = (
        f"Please refactor the following code based on the instruction provided.\n\n"
        f"INSTRUCTION: {refactoring_prompt}\n\n"
        f"ORIGINAL CODE:\n```python\n{original_code}\n```\n\n"
        f"Respond with ONLY the complete, refactored code. Do not add any commentary or explanations."
    )

    generation_result = await handle_code_generation({"prompt": full_prompt})
    if generation_result["status"] == "error":
        return generation_result

    refactored_code = generation_result["data"]

    write_result = await handle_write_file(
        {"filename": filename, "content": refactored_code},
        session_id=session_id
    )

    if write_result["status"] == "success":
        return {"status": "success", "data": f"Successfully refactored and saved '{filename}'."}
    else:
        return write_result

TOOL_DISPATCHER = {
    "final_answer": handle_final_answer,
    "execute_script": handle_execute_script,
    "git_clone": handle_git_clone,
    "git_commit_and_push": handle_git_commit_and_push,
    "code_generation": handle_code_generation,
    "write_file": handle_write_file,
    "read_file": handle_read_file,
    "list_files": handle_list_files,
    "refactor_code": handle_refactor_code,
}

async def execute_tool(tool: ToolModel, parameters: Dict[str, Any], session_id: str, user_prompt: str) -> Dict[str, Any]:
    tool_name = tool.name
    if tool_name in TOOL_DISPATCHER:
        return await TOOL_DISPATCHER[tool_name](parameters, session_id=session_id, user_prompt=user_prompt)
    else:
        return {"status": "error", "message": f"Tool '{tool_name}' not found."}

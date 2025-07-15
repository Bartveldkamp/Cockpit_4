import os
import json
import logging
import subprocess
import asyncio
from typing import Any, Dict, List
import git

from backend.llm_client import get_llm_response
from backend.vault import VAULT_ROOT
from backend.memory_manager import memory_manager
from backend.config import settings
from backend.schemas import ToolModel  # Ensure ToolModel is imported

logger = logging.getLogger(__name__)

# --- NEW AI SECURITY OFFICER ---
async def assess_command_risk(command: str, user_prompt: str) -> bool:
    """Uses an LLM to assess if a shell command is safe to execute."""
    # Simple, fast pre-filter for obviously safe commands
    safe_commands = ["ls", "cat", "pwd", "pip list", "echo"]
    if any(command.strip().startswith(safe_cmd) for safe_cmd in safe_commands):
        logger.info(f"Command '{command}' passed pre-filter as safe.")
        return True

    logger.info(f"Engaging AI Security Officer to assess command: '{command}'")

    security_prompt = (
        "You are an AI Security Officer. Your only job is to determine if a shell command is safe to execute in the context of a user's request. "
        "The command is considered 'SAFE' if it is not destructive (e.g., no `rm -rf`, `mv` on important files, `dd`), is not trying to access sensitive system files outside its workspace, and is directly related to the user's goal. "
        "The command is 'UNSAFE' if it is destructive, tries to escalate privileges (`sudo`), or is clearly unrelated to the goal.\n\n"
        f"User's Goal: \"{user_prompt}\"\n"
        f"Command to Assess: \"{command}\"\n\n"
        "Is this command SAFE or UNSAFE? Respond with ONLY the word SAFE or UNSAFE."
    )

    messages = [{"role": "system", "content": security_prompt}]

    response = await get_llm_response(
        provider="mistral", model_name="mistral-large-latest", messages=messages,
        temperature=0.0, max_tokens=5
    )

    is_safe = "SAFE" in response.upper()
    if is_safe:
        logger.info(f"Security Officer approved command: '{command}'")
    else:
        logger.warning(f"Security Officer REJECTED command: '{command}'")

    return is_safe

# --- Tool Definitions ---
def get_tool_definitions() -> List[Dict[str, Any]]:
    """Returns the schema for all available tools."""
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
    ]

# --- Tool Execution Logic ---
async def execute_tool(tool: ToolModel, parameters: Dict[str, Any], session_id: str, user_prompt: str) -> Dict[str, Any]:
    """Executes a tool and returns a standardized dictionary output."""
    session_vault_path = os.path.join(VAULT_ROOT, session_id)
    os.makedirs(session_vault_path, exist_ok=True)
    project_root_path = os.path.abspath(os.path.join(VAULT_ROOT, '..'))

    try:
        tool_name = tool.name
        if tool_name == "final_answer":
            answer = parameters.get("answer", "I have processed the request.")
            return {"status": "success", "data": answer}

        elif tool_name == "execute_script":
            command = parameters.get("command")
            if not command: return {"status": "error", "message": "Missing 'command' parameter."}

            working_dir_name = parameters.get("working_dir", ".")
            target_cwd = os.path.normpath(os.path.join(session_vault_path, working_dir_name))
            if not target_cwd.startswith(os.path.abspath(session_vault_path)):
                return {"status": "error", "message": "Directory traversal is not allowed."}
            if not os.path.isdir(target_cwd):
                return {"status": "error", "message": f"Working directory '{working_dir_name}' does not exist."}

            is_approved = await assess_command_risk(command, user_prompt)
            if not is_approved:
                return {"status": "error", "message": f"Execution of command '{command}' was denied by AI Security Officer."}

            logger.info(f"Executing AI-approved shell command: '{command}' in '{target_cwd}'")
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=target_cwd
            )
            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                return {"status": "success", "data": stdout.decode().strip()}
            else:
                return {"status": "error", "message": stderr.decode().strip(), "exit_code": process.returncode}

        elif tool_name == "git_clone":
            repo_url = parameters.get("repo_url")
            if not repo_url: return {"status": "error", "message": "Missing 'repo_url' parameter."}
            repo_name = repo_url.split('/')[-1].replace('.git', '')
            local_path = parameters.get("local_path", repo_name)
            clone_path = os.path.join(session_vault_path, local_path)
            if os.path.exists(clone_path): return {"status": "error", "message": f"Directory '{local_path}' already exists."}
            logger.info(f"Cloning repository from '{repo_url}' into '{clone_path}'...")
            git.Repo.clone_from(repo_url, clone_path)
            return {"status": "success", "data": f"Successfully cloned repository into '{local_path}'."}

        elif tool_name == "git_commit_and_push":
            repo_path = parameters.get("repo_path")
            commit_message = parameters.get("commit_message")
            if not repo_path or not commit_message: return {"status": "error", "message": "Missing 'repo_path' or 'commit_message'."}
            full_repo_path = os.path.join(session_vault_path, repo_path)
            if not os.path.isdir(full_repo_path): return {"status": "error", "message": f"Repository path '{repo_path}' does not exist."}
            logger.info(f"Committing and pushing changes in '{full_repo_path}'...")
            repo = git.Repo(full_repo_path)
            repo.git.add(A=True)
            if not repo.is_dirty(untracked_files=True): return {"status": "success", "data": "No changes to commit."}
            repo.index.commit(commit_message)
            origin = repo.remote(name='origin')
            push_info = origin.push()
            if any(p.flags & git.PushInfo.ERROR for p in push_info):
                error_summary = "\n".join([str(p.summary) for p in push_info if p.flags & git.PushInfo.ERROR])
                return {"status": "error", "message": f"Failed to push to remote: {error_summary}"}
            return {"status": "success", "data": f"Successfully committed and pushed changes with message: '{commit_message}'."}

        elif tool_name == "code_generation":
            prompt = parameters.get("prompt")
            if not prompt: return {"status": "error", "message": "Missing 'prompt'."}
            code_gen_system_prompt = "You are a code generation engine..."
            code_string = await get_llm_response(
                provider="mistral", model_name="codestral-latest",
                messages=[{"role": "system", "content": code_gen_system_prompt}, {"role": "user", "content": prompt}],
                temperature=0.0, top_p=1.0, max_tokens=4096, stop_tokens=[]
            )
            return {"status": "success", "data": code_string}

        elif tool_name == "write_file":
            filename = parameters.get("filename")
            content = parameters.get("content", "")
            if not filename: return {"status": "error", "message": "Missing 'filename'."}
            file_path = os.path.join(session_vault_path, filename)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f: f.write(content)
            memory_manager.add_to_memory(content=content, filename=filename, session_id=session_id)
            return {"status": "success", "data": f"Successfully wrote {len(content.encode('utf-8'))} bytes to '{filename}'."}

        elif tool_name == "read_file":
            filename = parameters.get("filename")
            if not filename: return {"status": "error", "message": "Missing 'filename'."}
            session_file_path = os.path.join(session_vault_path, filename)
            root_file_path = os.path.join(project_root_path, filename)
            if os.path.exists(session_file_path): file_path_to_read = session_file_path
            elif os.path.exists(root_file_path): file_path_to_read = root_file_path
            else: return {"status": "error", "message": f"File '{filename}' not found in session vault or project root."}
            with open(file_path_to_read, 'r', encoding='utf-8') as f: content = f.read()
            return {"status": "success", "data": content}

        elif tool_name == "list_files":
            if not os.path.exists(session_vault_path): return {"status": "success", "data": "No files in session."}
            files = [f for f in os.listdir(session_vault_path) if os.path.isfile(os.path.join(session_vault_path, f))]
            if not files: return {"status": "success", "data": "No files in session."}
            return {"status": "success", "data": "\n".join(files)}

        else:
            return {"status": "error", "message": f"Tool '{tool_name}' not found."}

    except Exception as e:
        logger.error(f"Error in tool '{tool_name}': {e}", exc_info=True)
        return {"status": "error", "message": f"An unexpected error occurred: {str(e)}"}

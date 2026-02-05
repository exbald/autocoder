"""
Dev Server Router
=================

API endpoints for dev server control (start/stop) and configuration.
Uses project registry for path lookups and project_config for command detection.
"""

import logging
import sys
import shlex
from pathlib import Path

from fastapi import APIRouter, HTTPException

from ..schemas import (
    DevServerActionResponse,
    DevServerConfigResponse,
    DevServerConfigUpdate,
    DevServerStartRequest,
    DevServerStatus,
)
from ..services.dev_server_manager import get_devserver_manager
from ..services.project_config import (
    clear_dev_command,
    get_dev_command,
    get_project_config,
    set_dev_command,
)
from ..utils.project_helpers import get_project_path as _get_project_path
from ..utils.validation import validate_project_name

# Add root to path for security module import
_root = Path(__file__).parent.parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from security import extract_commands, get_effective_commands, is_command_allowed

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/api/projects/{project_name}/devserver", tags=["devserver"])


def get_project_dir(project_name: str) -> Path:
    """
    Get the validated project directory for a project name.

    Args:
        project_name: Name of the project

    Returns:
        Path to the project directory

    Raises:
        HTTPException: If project is not found or directory does not exist
    """
    project_name = validate_project_name(project_name)
    project_dir = _get_project_path(project_name)

    if not project_dir:
        raise HTTPException(
            status_code=404,
            detail=f"Project '{project_name}' not found in registry"
        )

    if not project_dir.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Project directory not found: {project_dir}"
        )

    return project_dir

ALLOWED_RUNNERS = {"npm", "pnpm", "yarn", "uvicorn", "python", "python3"}

def validate_custom_command_strict(cmd: str) -> None:
    """
    Strict allowlist validation for dev server commands.
    Prevents arbitrary command execution (no sh -c, no cmd /c, no python -c, etc.)
    """
    if not isinstance(cmd, str) or not cmd.strip():
        raise ValueError("custom_command cannot be empty")

    argv = shlex.split(cmd, posix=(sys.platform != "win32"))
    if not argv:
        raise ValueError("custom_command could not be parsed")

    base = Path(argv[0]).name.lower()

    # Block direct shells / interpreters commonly used for command injection
    if base in {"sh", "bash", "zsh", "cmd", "powershell", "pwsh"}:
        raise ValueError(f"custom_command runner not allowed: {base}")

    if base not in ALLOWED_RUNNERS:
        raise ValueError(f"custom_command runner not allowed: {base}")

    # Block one-liner execution
    lowered = [a.lower() for a in argv]
    if base in {"python", "python3"}:
        if "-c" in lowered:
            raise ValueError("python -c is not allowed")
        # Only allow: python -m uvicorn ...
        if len(argv) < 3 or argv[1:3] != ["-m", "uvicorn"]:
            raise ValueError("Only 'python -m uvicorn ...' is allowed")

    if base == "uvicorn":
        if len(argv) < 2 or ":" not in argv[1]:
            raise ValueError("uvicorn must specify an app like module:app")

        allowed_flags = {"--host", "--port", "--reload", "--log-level", "--workers"}
        i = 2
        while i < len(argv):
            a = argv[i]
            if a.startswith("-") and a not in allowed_flags:
                raise ValueError(f"uvicorn flag not allowed: {a}")
            i += 1

    if base in {"npm", "pnpm", "yarn"}:
        # Allow only dev/start scripts (no arbitrary exec)
        if base == "npm":
            if len(argv) < 3 or argv[1] != "run" or argv[2] not in {"dev", "start"}:
                raise ValueError("npm custom_command must be 'npm run dev' or 'npm run start'")
        elif base == "pnpm":
            ok = (len(argv) >= 2 and argv[1] in {"dev", "start"}) or (len(argv) >= 3 and argv[1] == "run" and argv[2] in {"dev", "start"})
            if not ok:
                raise ValueError("pnpm custom_command must be 'pnpm dev/start' or 'pnpm run dev/start'")
        elif base == "yarn":
            ok = (len(argv) >= 2 and argv[1] in {"dev", "start"}) or (len(argv) >= 3 and argv[1] == "run" and argv[2] in {"dev", "start"})
            if not ok:
                raise ValueError("yarn custom_command must be 'yarn dev/start' or 'yarn run dev/start'")


def get_project_devserver_manager(project_name: str):
    """
    Get the dev server process manager for a project.

    Args:
        project_name: Name of the project

    Returns:
        DevServerProcessManager instance for the project

    Raises:
        HTTPException: If project is not found or directory does not exist
    """
    project_dir = get_project_dir(project_name)
    return get_devserver_manager(project_name, project_dir)


def validate_dev_command(command: str, project_dir: Path) -> None:
    """
    Validate a dev server command against the security allowlist.

    Extracts all commands from the shell string and checks each against
    the effective allowlist (global + org + project). Raises HTTPException
    if any command is blocked or not allowed.

    Args:
        command: The shell command string to validate
        project_dir: Project directory for loading project-level allowlists

    Raises:
        HTTPException 400: If the command fails validation
    """
    commands = extract_commands(command)
    if not commands:
        raise HTTPException(
            status_code=400,
            detail="Could not parse command for security validation"
        )

    allowed_commands, blocked_commands = get_effective_commands(project_dir)

    for cmd in commands:
        if cmd in blocked_commands:
            logger.warning("Blocked dev server command '%s' (in blocklist) for project dir %s", cmd, project_dir)
            raise HTTPException(
                status_code=400,
                detail=f"Command '{cmd}' is blocked and cannot be used as a dev server command"
            )
        if not is_command_allowed(cmd, allowed_commands):
            logger.warning("Rejected dev server command '%s' (not in allowlist) for project dir %s", cmd, project_dir)
            raise HTTPException(
                status_code=400,
                detail=f"Command '{cmd}' is not in the allowed commands list"
            )


# ============================================================================
# Endpoints
# ============================================================================


@router.get("/status", response_model=DevServerStatus)
async def get_devserver_status(project_name: str) -> DevServerStatus:
    """
    Get the current status of the dev server for a project.

    Returns information about whether the dev server is running,
    its process ID, detected URL, and the command used to start it.
    """
    manager = get_project_devserver_manager(project_name)

    # Run healthcheck to detect crashed processes
    await manager.healthcheck()

    return DevServerStatus(
        status=manager.status,
        pid=manager.pid,
        url=manager.detected_url,
        command=manager._command,
        started_at=manager.started_at.isoformat() if manager.started_at else None,
    )


@router.post("/start", response_model=DevServerActionResponse)
async def start_devserver(
    project_name: str,
    request: DevServerStartRequest = DevServerStartRequest(),
) -> DevServerActionResponse:
    """
    Start the dev server for a project.

    If a custom command is provided in the request, it will be used.
    Otherwise, the effective command from the project configuration is used.

    Args:
        project_name: Name of the project
        request: Optional start request with custom command

    Returns:
        Response indicating success/failure and current status
    """
    manager = get_project_devserver_manager(project_name)
    project_dir = get_project_dir(project_name)

    # Determine which command to use
    command: str | None
    if request.command:
        raise HTTPException(
            status_code=400,
            detail="Direct command execution is disabled. Use /config to set a safe custom_command."
        )
    
    command = get_dev_command(project_dir)

    if not command:
        raise HTTPException(
            status_code=400,
            detail="No dev command available. Configure a custom command or ensure project type can be detected."
        )

    # Validate command against security allowlist before execution
    validate_dev_command(command, project_dir)

    # Now command is definitely str and validated
    success, message = await manager.start(command)

    return DevServerActionResponse(
        success=success,
        status=manager.status,
        message=message,
    )


@router.post("/stop", response_model=DevServerActionResponse)
async def stop_devserver(project_name: str) -> DevServerActionResponse:
    """
    Stop the dev server for a project.

    Gracefully terminates the dev server process and all its child processes.

    Args:
        project_name: Name of the project

    Returns:
        Response indicating success/failure and current status
    """
    manager = get_project_devserver_manager(project_name)

    success, message = await manager.stop()

    return DevServerActionResponse(
        success=success,
        status=manager.status,
        message=message,
    )


@router.get("/config", response_model=DevServerConfigResponse)
async def get_devserver_config(project_name: str) -> DevServerConfigResponse:
    """
    Get the dev server configuration for a project.

    Returns information about:
    - detected_type: The auto-detected project type (nodejs-vite, python-django, etc.)
    - detected_command: The default command for the detected type
    - custom_command: Any user-configured custom command
    - effective_command: The command that will actually be used (custom or detected)

    Args:
        project_name: Name of the project

    Returns:
        Configuration details for the project's dev server
    """
    project_dir = get_project_dir(project_name)
    config = get_project_config(project_dir)

    return DevServerConfigResponse(
        detected_type=config["detected_type"],
        detected_command=config["detected_command"],
        custom_command=config["custom_command"],
        effective_command=config["effective_command"],
    )


@router.patch("/config", response_model=DevServerConfigResponse)
async def update_devserver_config(
    project_name: str,
    update: DevServerConfigUpdate,
) -> DevServerConfigResponse:
    """
    Update the dev server configuration for a project.

    Set custom_command to a string to override the auto-detected command.
    Set custom_command to null/None to clear the custom command and revert
    to using the auto-detected command.

    Args:
        project_name: Name of the project
        update: Configuration update containing the new custom_command

    Returns:
        Updated configuration details for the project's dev server
    """
    project_dir = get_project_dir(project_name)

    # Update the custom command
    if update.custom_command is None:
        # Clear the custom command
        try:
            clear_dev_command(project_dir)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    else:
        # Validate command against security allowlist before persisting
        validate_dev_command(update.custom_command, project_dir)

        # Set the custom command
        try:
            validate_custom_command_strict(update.custom_command)
            set_dev_command(project_dir, update.custom_command)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except OSError as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to save configuration: {e}"
            )

    # Return updated config
    config = get_project_config(project_dir)

    return DevServerConfigResponse(
        detected_type=config["detected_type"],
        detected_command=config["detected_command"],
        custom_command=config["custom_command"],
        effective_command=config["effective_command"],
    )

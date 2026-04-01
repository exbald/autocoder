#!/usr/bin/env python3
import os
import sys
import subprocess

# Force binding to 0.0.0.0 for Docker accessibility
os.environ["HOST"] = "0.0.0.0"
os.environ["PORT"] = "8888"

# Run the original start_ui with modified args
sys.path.insert(0, "/app")

# Import and run with modifications
import asyncio
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from pathlib import Path
ROOT = Path("/app")

# Start uvicorn directly with 0.0.0.0 binding
venv_python = Path("/app/venv/bin/python")
if not venv_python.exists():
    venv_python = Path("python")

cmd = [
    str(venv_python), "-m", "uvicorn",
    "server.main:app",
    "--host", "0.0.0.0",
    "--port", "8888"
]

print("Starting AutoCoder with 0.0.0.0 binding for Docker...")
print("UI will be available at port 8888")
subprocess.run(cmd, cwd=str(ROOT))

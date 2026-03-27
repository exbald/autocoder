"""
Authentication Error Detection
==============================

Shared utilities for detecting Claude CLI authentication errors.
Used by both CLI (start.py) and server (process_manager.py) to provide
consistent error detection and messaging.
"""

import re

# Patterns that indicate authentication errors from Claude CLI
AUTH_ERROR_PATTERNS = [
    r"not\s+logged\s+in",
    r"not\s+authenticated",
    r"authentication\s+(failed|required|error)",
    r"login\s+required",
    r"please\s+(run\s+)?['\"]?claude\s+login",
    r"unauthorized",
    r"invalid\s+(token|credential|api.?key)",
    r"expired\s+(token|session|credential)",
    r"could\s+not\s+authenticate",
    r"sign\s+in\s+(to|required)",
]


def is_auth_error(text: str) -> bool:
    """
    Check if text contains Claude CLI authentication error messages.

    Uses case-insensitive pattern matching against known error messages.

    Args:
        text: Output text to check

    Returns:
        True if any auth error pattern matches, False otherwise
    """
    if not text:
        return False
    text_lower = text.lower()
    for pattern in AUTH_ERROR_PATTERNS:
        if re.search(pattern, text_lower):
            return True
    return False


# CLI-style help message (for terminal output)
AUTH_ERROR_HELP_CLI = """
==================================================
  Authentication Error Detected
==================================================

Claude CLI requires authentication to work.

Option 1 (Recommended): Set an API key
  export ANTHROPIC_API_KEY=your-key-here
  Get a key at: https://console.anthropic.com/

Option 2: Use subscription login
  claude login

  Note: Anthropic's policy may not permit using
  subscription auth with third-party agents.
  API key authentication is recommended.
==================================================
"""

# Server-style help message (for WebSocket streaming)
AUTH_ERROR_HELP_SERVER = """
================================================================================
  AUTHENTICATION ERROR DETECTED
================================================================================

Claude CLI requires authentication to work.

Option 1 (Recommended): Set an API key
  export ANTHROPIC_API_KEY=your-key-here
  Get a key at: https://console.anthropic.com/

Option 2: Use subscription login
  claude login

  Note: Anthropic's policy may not permit using
  subscription auth with third-party agents.
  API key authentication is recommended.
================================================================================
"""


def print_auth_error_help() -> None:
    """Print helpful message when authentication error is detected (CLI version)."""
    print(AUTH_ERROR_HELP_CLI)

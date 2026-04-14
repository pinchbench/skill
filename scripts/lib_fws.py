"""
fws lifecycle management for GWS-based tasks.

Starts/stops the fws server and configures environment variables
so that gws CLI commands are redirected to the local mock.
"""

import logging
import os
import shutil
import subprocess
import time

logger = logging.getLogger("pinchbench")

# Environment variables that fws sets
MOCK_GWS_ENV_KEYS = [
    "GOOGLE_WORKSPACE_CLI_CONFIG_DIR",
    "GOOGLE_WORKSPACE_CLI_TOKEN",
    "HTTPS_PROXY",
    "SSL_CERT_FILE",
]


def is_fws_task(frontmatter: dict) -> bool:
    """Check if a task requires fws (category is gws/github or prerequisites include fws)."""
    if frontmatter.get("category") in ("gws", "github"):
        return True
    prereqs = frontmatter.get("prerequisites", [])
    return any("fws" in str(p) for p in prereqs)


def fws_available() -> bool:
    """Check if fws CLI is available."""
    return shutil.which("fws") is not None


def start_fws() -> dict:
    """Start the fws server and set environment variables.

    Returns a dict of the original env var values (for restoration).
    """
    logger.info("🔧 Starting fws server...")

    # Stop any existing server
    subprocess.run(["fws", "server", "stop"], capture_output=True, check=False)
    time.sleep(0.3)

    # Start server
    result = subprocess.run(
        ["fws", "server", "start"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    if result.returncode != 0:
        logger.error("Failed to start fws: %s", result.stderr)
        raise RuntimeError(f"fws server start failed: {result.stderr}")

    # Parse the env vars from output
    env_vars = {}
    for line in result.stdout.splitlines():
        line = line.strip()
        if line.startswith("export "):
            line = line[7:]
        if "=" in line and any(key in line for key in MOCK_GWS_ENV_KEYS):
            key, _, value = line.partition("=")
            env_vars[key.strip()] = value.strip()

    if not env_vars:
        # Fallback: use default paths
        home = os.path.expanduser("~")
        env_vars = {
            "GOOGLE_WORKSPACE_CLI_CONFIG_DIR": f"{home}/.local/share/fws/config",
            "GOOGLE_WORKSPACE_CLI_TOKEN": "fake",
            "HTTPS_PROXY": "http://localhost:4101",
            "SSL_CERT_FILE": f"{home}/.local/share/fws/certs/ca.crt",
        }

    # Save original values and set new ones
    original_env = {}
    for key, value in env_vars.items():
        original_env[key] = os.environ.get(key)
        os.environ[key] = value

    logger.info("✅ fws server started, env configured")
    return original_env


def stop_fws(original_env: dict) -> None:
    """Stop the fws server and restore original environment variables."""
    logger.info("🔧 Stopping fws server...")

    subprocess.run(["fws", "server", "stop"], capture_output=True, check=False)

    # Restore original env
    for key, value in original_env.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value

    logger.info("✅ fws server stopped, env restored")

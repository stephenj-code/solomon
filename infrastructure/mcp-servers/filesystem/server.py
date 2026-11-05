#!/usr/bin/env python3
"""
solomon-filesystem — MCP server for file I/O and shell commands on cluster nodes.

Tools:
  read_file   — read a file (local or via SSH to remote nodes)
  write_file  — write/overwrite a file
  patch_file  — targeted string replacement in a file
  list_dir    — list directory contents
  run_shell   — run a shell command locally or on a remote node
  node_exec   — explicitly run a command on a named cluster node via SSH

The pod runs on agx-orin-prod-1 with hostPath mounts:
  /repos → /home/stephen/repos   (git repositories; default cwd for run_shell)
  /data  → /data                 (Frigate NVR data, model artifacts)

Remote nodes (orin-nano-prod-1, orin-nano-dev-1) are accessed via SSH.
SSH private key: /app/secrets/ssh-key (mounted from filesystem-ssh-key Secret).
  RUNTIME: seal SSH key → infrastructure/mcp-servers/filesystem/sealed-secrets/filesystem-ssh-key-sealed.yaml

Executed on-demand via `kubectl exec` by scripts/mcp-proxy.py — stdio transport.
"""

import json
import os
import subprocess
from pathlib import Path

import paramiko
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("solomon-filesystem")

SSH_KEY_PATH = "/app/secrets/ssh-key"
SSH_USER = os.environ.get("SSH_USER", "stephen")

# Node → IP mapping. None = local (this pod runs on agx-orin-prod-1).
NODE_IPS: dict[str, str | None] = {
    "agx-orin-prod-1": None,
    "orin-nano-prod-1": "192.168.1.175",
    "orin-nano-dev-1": "192.168.1.139",
}


def _is_local(node: str) -> bool:
    return not node or node == "agx-orin-prod-1"


def _ssh_run(node: str, command: str) -> str:
    ip = NODE_IPS.get(node)
    if ip is None:
        return f"Error: unknown node '{node}'. Valid: {list(NODE_IPS)}"
    if not Path(SSH_KEY_PATH).exists():
        return (
            f"Error: SSH key not found at {SSH_KEY_PATH}. "
            "Seal filesystem-ssh-key Secret (RUNTIME task) and restart the pod."
        )
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(
            hostname=ip,
            username=SSH_USER,
            key_filename=SSH_KEY_PATH,
            timeout=30,
        )
        _, stdout, stderr = client.exec_command(command, timeout=60)
        out = stdout.read().decode()
        err = stderr.read().decode()
        exit_code = stdout.channel.recv_exit_status()
        client.close()
        result = out
        if err:
            result += f"\n[stderr]\n{err}"
        if exit_code != 0:
            result += f"\n[exit code: {exit_code}]"
        return result
    except Exception as e:
        return f"Error connecting to {node} ({ip}): {e}"


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def read_file(path: str, node: str = "") -> str:
    """
    Read a file. Leave node empty for agx-orin-prod-1 (local).
    Remote nodes: orin-nano-prod-1, orin-nano-dev-1.
    Local mounted paths: /repos (→ /home/stephen/repos), /data.
    """
    if _is_local(node):
        try:
            return Path(path).read_text()
        except Exception as e:
            return f"Error: {e}"
    return _ssh_run(node, f"cat {path!r}")


@mcp.tool()
def write_file(path: str, content: str, node: str = "") -> str:
    """
    Write content to a file, creating parent directories as needed.
    Leave node empty for local (agx-orin-prod-1).
    """
    if _is_local(node):
        try:
            p = Path(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)
            return f"Written: {path} ({len(content)} bytes)"
        except Exception as e:
            return f"Error: {e}"
    # Remote: use printf to avoid heredoc escaping issues
    escaped = content.replace("\\", "\\\\").replace("'", "'\\''")
    cmd = f"mkdir -p {str(Path(path).parent)!r} && printf '%s' '{escaped}' > {path!r}"
    return _ssh_run(node, cmd)


@mcp.tool()
def patch_file(path: str, old_string: str, new_string: str, node: str = "") -> str:
    """
    Replace the first occurrence of old_string with new_string in a file.
    Returns an error if old_string is not found.
    """
    if _is_local(node):
        try:
            p = Path(path)
            content = p.read_text()
            if old_string not in content:
                return f"Error: old_string not found in {path}"
            p.write_text(content.replace(old_string, new_string, 1))
            return f"Patched: {path}"
        except Exception as e:
            return f"Error: {e}"
    # Remote: read → patch → write back
    current = _ssh_run(node, f"cat {path!r}")
    if old_string not in current:
        return f"Error: old_string not found in {path} on {node}"
    return write_file(path, current.replace(old_string, new_string, 1), node)


@mcp.tool()
def list_dir(path: str, node: str = "") -> str:
    """
    List directory contents as JSON (local) or ls -la output (remote).
    Leave node empty for local (agx-orin-prod-1).
    """
    if _is_local(node):
        try:
            entries = []
            for entry in sorted(Path(path).iterdir()):
                stat = entry.stat()
                entries.append({
                    "name": entry.name,
                    "type": "dir" if entry.is_dir() else "file",
                    "size": stat.st_size if entry.is_file() else None,
                })
            return json.dumps(entries, indent=2)
        except Exception as e:
            return f"Error: {e}"
    return _ssh_run(node, f"ls -la {path!r}")


@mcp.tool()
def run_shell(command: str, cwd: str = "/repos/solomon", node: str = "") -> str:
    """
    Run a shell command. Default cwd is /repos/solomon (the platform repo mount).
    Leave node empty to run locally on agx-orin-prod-1.
    For remote nodes, cwd is ignored (SSH handles it via the command string).
    """
    if _is_local(node):
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=60,
            )
            out = result.stdout
            if result.stderr:
                out += f"\n[stderr]\n{result.stderr}"
            if result.returncode != 0:
                out += f"\n[exit code: {result.returncode}]"
            return out or "(no output)"
        except subprocess.TimeoutExpired:
            return "Error: command timed out after 60s"
        except Exception as e:
            return f"Error: {e}"
    return _ssh_run(node, command)


@mcp.tool()
def node_exec(node: str, command: str) -> str:
    """
    Run a command on a named cluster node.
    Nodes: agx-orin-prod-1 (local), orin-nano-prod-1, orin-nano-dev-1.
    agx-orin-prod-1 runs locally (no SSH); others go via SSH.
    """
    if _is_local(node):
        return run_shell(command, cwd="/")
    return _ssh_run(node, command)


if __name__ == "__main__":
    mcp.run(transport="stdio")

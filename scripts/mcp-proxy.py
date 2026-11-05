#!/usr/bin/env python3
"""
MCP proxy — bridges Claude Code (stdio) to in-cluster MCP server pods via kubectl exec.

Usage: python3 scripts/mcp-proxy.py <server>
  server: kubernetes | prometheus | filesystem

Each Claude Code session runs this script once per MCP server. The script finds the
running pod for that server in the mcp-servers namespace, then replaces itself with
`kubectl exec -i <pod> -- python /app/server.py`.

The os.execlp call transfers the current process's stdin/stdout directly to kubectl,
making the stdio channel the MCP protocol transport. When Claude Code disconnects,
stdin closes, the remote server.py exits, and kubectl exits cleanly.

Prerequisites:
  - kubectl configured with access to the cluster (kubeconfig or in-cluster)
  - MCP server pods running in mcp-servers namespace (deployed by ArgoCD)
  - PYTHONPATH=/app/lib set in container env (packages installed by initContainer)
"""

import os
import subprocess
import sys

SERVER_LABELS = {
    "kubernetes": "solomon-kubernetes",
    "prometheus": "solomon-prometheus",
    "filesystem": "solomon-filesystem",
}


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in SERVER_LABELS:
        names = " | ".join(SERVER_LABELS)
        print(f"Usage: {sys.argv[0]} <{names}>", file=sys.stderr)
        sys.exit(1)

    server = sys.argv[1]
    app_label = SERVER_LABELS[server]

    # Find the first Running pod for this server
    result = subprocess.run(
        [
            "kubectl", "get", "pod",
            "-n", "mcp-servers",
            "-l", f"app={app_label}",
            "--field-selector=status.phase=Running",
            "-o", "jsonpath={.items[0].metadata.name}",
        ],
        capture_output=True,
        text=True,
    )
    pod_name = result.stdout.strip()

    if not pod_name:
        print(
            f"Error: no Running pod found for app={app_label} in namespace mcp-servers.\n"
            f"  Check: kubectl get pods -n mcp-servers -l app={app_label}\n"
            f"  Stderr: {result.stderr.strip()}",
            file=sys.stderr,
        )
        sys.exit(1)

    # Replace this process with kubectl exec.
    # stdin/stdout are inherited → MCP protocol flows over this channel.
    # PYTHONPATH is set in the container env (initContainer installed packages to /app/lib).
    os.execlp(
        "kubectl",
        "kubectl", "exec", "-i",
        "-n", "mcp-servers",
        pod_name,
        "--",
        "python", "/app/server.py",
    )


if __name__ == "__main__":
    main()

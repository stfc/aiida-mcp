"""Detection of a locally running AiiDAlab Jupyter server.

Assumes the MCP server runs as the same user and in the same Python
environment as the AiiDAlab Jupyter server, e.g. started by the container's
entrypoint script alongside it.
"""

from typing import Any


def get_status() -> dict[str, Any]:
    """Report whether an AiiDAlab server is running locally, and its URL.

    Returns
    -------
    dict[str, Any]
        Whether a server is running and, if so, its URL (with access token),
        pid, root directory and version. If several candidate servers are
        running and none is clearly AiiDAlab, ``ambiguous`` is True and
        ``servers`` lists all of them instead.
    """
    try:
        from jupyter_server.serverapp import list_running_servers
    except ImportError:
        return {"running": False, "error": "jupyter_server is not installed"}

    servers = list(list_running_servers())
    if not servers:
        return {"running": False}

    matches = [s for s in servers if "aiidalab" in s.get("root_dir", "").lower()]
    if not matches:
        # None matched by working directory; fall back to whatever is running.
        # In an AiiDAlab container there is normally only one Jupyter server.
        matches = servers

    if len(matches) > 1:
        return {
            "running": True,
            "ambiguous": True,
            "servers": [_server_summary(server) for server in matches],
        }

    return {"running": True, **_server_summary(matches[0])}


def _server_summary(server: dict[str, Any]) -> dict[str, Any]:
    token = server.get("token")
    url = server["url"]
    return {
        "url": f"{url}?token={token}" if token else url,
        "pid": server.get("pid"),
        "root_dir": server.get("root_dir"),
        "version": server.get("version"),
    }

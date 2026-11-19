"""Plugin tools discovered via the ``aiida_mcp.plugins`` entry point group.

Any installed package can expose calcjob-specific MCP tools by declaring, in its own
``pyproject.toml``, an entry point in the ``aiida_mcp.plugins`` group that points at a
module providing ``is_available() -> bool`` and ``register(mcp) -> None``, e.g.::

    [project.entry-points."aiida_mcp.plugins"]
    dlpoly = "aiida_dlpoly.mcp"

aiida-mcp bundles its own plugin modules for dlpoly, chemshell and mlip (see
``aiida_mcp/plugins/{dlpoly,chemshell,mlip}.py``), registered through this same
mechanism via the entry points declared in this project's own ``pyproject.toml``.
"""

import importlib
from importlib.metadata import entry_points

from aiida.plugins import entry_point
from mcp.server.mcpserver import MCPServer

ENTRY_POINT_GROUP = "aiida_mcp.plugins"


def register_all(mcp: MCPServer) -> list[str]:
    """Register the tools of every installed plugin and return the ones registered.

    Parameters
    ----------
    mcp : MCPServer
        The server to register plugin tools on.

    Returns
    -------
    list[str]
        Names of the ``aiida_mcp.plugins`` entry points that were registered.
    """
    registered = []
    for ep in entry_points(group=ENTRY_POINT_GROUP):
        module = ep.load()
        if module.is_available():
            module.register(mcp)
            registered.append(ep.name)
    return registered


def clear_entry_point_cache() -> None:
    """Clear cached entry point lookups so newly installed plugins can be found.

    AiiDA caches entry point lookups (``aiida.plugins.entry_point.eps``/``eps_select``)
    for the lifetime of the process, and Python's import system caches which
    directories/distributions exist on ``sys.path``. A plugin package installed after
    the server started would otherwise never be detected as available. Call this
    before `register_all` to pick up newly installed plugins.
    """
    importlib.invalidate_caches()
    entry_point.eps.cache_clear()
    entry_point.eps_select.cache_clear()

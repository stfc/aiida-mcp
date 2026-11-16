"""Plugin-specific calcjob tools, registered only if their entry point is installed."""

import importlib

from aiida.plugins import entry_point
from mcp.server.mcpserver import MCPServer

# Each plugin module provides `is_available()` and `register(mcp)`.
PLUGIN_MODULES = (
    "aiida_mcp.plugins.dlpoly",
    "aiida_mcp.plugins.chemshell",
    "aiida_mcp.plugins.mlip",
)


def register_all(mcp: MCPServer) -> list[str]:
    """Register the tools of every installed plugin and return the ones registered.

    Parameters
    ----------
    mcp : MCPServer
        The server to register plugin tools on.

    Returns
    -------
    list[str]
        Dotted module names of the plugins that were registered.
    """
    registered = []
    for name in PLUGIN_MODULES:
        module = importlib.import_module(name)
        if module.is_available():
            module.register(mcp)
            registered.append(name)
    return registered


def clear_entry_point_cache() -> None:
    """Clear AiiDA's cached list of installed entry points.

    AiiDA caches entry point lookups (``aiida.plugins.entry_point.eps``/``eps_select``)
    for the lifetime of the process, so a plugin package installed after the server
    started would otherwise never be detected as available. Call this before
    `register_all` to pick up newly installed plugins.
    """
    entry_point.eps.cache_clear()
    entry_point.eps_select.cache_clear()

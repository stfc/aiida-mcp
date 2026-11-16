"""Plugin-specific calcjob tools, registered only if their entry point is installed."""

import importlib

from mcp.server.mcpserver import MCPServer

# Each plugin module provides `is_available()` and `register(mcp)`.
PLUGIN_MODULES = (
    "aiida_mcp.plugins.dlpoly",
    "aiida_mcp.plugins.chemshell",
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

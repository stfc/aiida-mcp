import importlib

from mcp.server.mcpserver import MCPServer

# Each plugin module provides `is_available()` and `register(mcp)`.
PLUGIN_MODULES = ("aiida_mcp.plugins.dlpoly",)


def register_all(mcp: MCPServer) -> list[str]:
    """Register the tools of every installed plugin and return the modules that were registered."""
    registered = []
    for name in PLUGIN_MODULES:
        module = importlib.import_module(name)
        if module.is_available():
            module.register(mcp)
            registered.append(name)
    return registered

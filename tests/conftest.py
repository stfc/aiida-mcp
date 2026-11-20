"""Shared pytest configuration for the test suite."""

import types
from unittest import mock

from mcp.server.mcpserver import MCPServer

pytest_plugins = ["aiida.tools.pytest_fixtures"]


def fake_plugin_module(*, available: bool = True):
    """Build a fake plugin module and a mutable state dict controlling is_available().

    Used to exercise `aiida_mcp.plugins.register_all`/`rescan_plugins` without
    depending on any real AiiDA plugin package being installed.
    """
    module = types.ModuleType("_fake_plugin")
    state = {"available": available}
    module.is_available = lambda: state["available"]

    def register(mcp: MCPServer) -> None:
        @mcp.tool()
        def fake_tool() -> str:
            """Register a fake tool, only for testing plugin discovery."""
            return "ok"

    module.register = register
    return module, state


def fake_entry_point(name: str, module: types.ModuleType):
    """Build a fake `importlib.metadata.EntryPoint`-like object loading `module`."""
    ep = mock.Mock()
    ep.name = name
    ep.load.return_value = module
    return ep

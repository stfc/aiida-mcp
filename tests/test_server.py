"""Tests for the MCP server's tool registration and error handling."""

import asyncio
from unittest import mock

import pytest
from conftest import fake_entry_point, fake_plugin_module
from mcp.server.mcpserver.exceptions import ToolError

from aiida_mcp import plugins, server


def test_all_tools_are_registered():
    """Every tool defined in server.py is exposed to MCP clients.

    DL_POLY and ChemShell tools are no longer bundled with aiida-mcp — they come from
    aiida-dlpoly's and aiida-chemshell's own optional ``mcp`` extras (see each
    repository's tests/test_mcp.py), which this environment does not install. aiida-mlip
    is also not installed here: its dependency tree is large, and the mlip test suite
    already covers its glue logic via fake modules (see tests/test_mlip_submit.py).
    None of these plugins' tools are expected here as a result — only the core,
    always-present tools are.
    """
    names = {tool.name for tool in asyncio.run(server.mcp.list_tools())}
    assert names == {
        "ping",
        "get_status",
        "list_processes",
        "get_process",
        "get_process_report",
        "list_computers",
        "list_codes",
        "query_nodes",
        "get_node_content",
        "get_aiidalab_status",
        "list_profiles",
        "rescan_plugins",
    }


def test_tool_error_message_reaches_client():
    """A ToolError's message reaches the client without a traceback."""
    with pytest.raises(ToolError) as excinfo:
        asyncio.run(server.mcp.call_tool("get_process", {"pk": 999999}))
    assert "No node with pk 999999" in str(excinfo.value)
    assert "Traceback" not in str(excinfo.value)


def test_rescan_plugins_reports_no_new_plugins_when_nothing_changed():
    """rescan_plugins reports nothing new when the available plugins are unchanged."""
    result = server.rescan_plugins()
    assert result["newly_registered"] == []


def test_rescan_plugins_detects_a_plugin_that_is_newly_available(monkeypatch):
    """rescan_plugins reports and registers a plugin that has since become available."""
    module, _ = fake_plugin_module()
    monkeypatch.setattr(
        plugins, "entry_points", lambda group: [fake_entry_point("fake", module)]
    )
    monkeypatch.setattr(
        server,
        "_registered_plugins",
        [name for name in server._registered_plugins if name != "fake"],
    )

    result = server.rescan_plugins()

    assert "fake" in result["newly_registered"]
    assert "fake" in result["available"]


def test_rescan_plugins_clears_the_entry_point_cache():
    """rescan_plugins clears AiiDA's entry point cache before re-registering."""
    with mock.patch.object(plugins, "clear_entry_point_cache") as clear_cache:
        server.rescan_plugins()
    clear_cache.assert_called_once()

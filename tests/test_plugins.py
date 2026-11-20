"""Tests for the generic plugin registration and describe/submit helpers."""

import asyncio
from importlib.metadata import entry_points
from unittest import mock

import pytest
from conftest import fake_entry_point, fake_plugin_module
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from aiida_mcp import plugins
from aiida_mcp.plugins import calcjob, workflow


def _tool_names(server: MCPServer) -> set[str]:
    return {tool.name for tool in asyncio.run(server.list_tools())}


def test_describe_unknown_plugin_is_tool_error():
    """Describing an uninstalled plugin is a ToolError."""
    with pytest.raises(ToolError, match="not installed"):
        calcjob.describe_calcjob("no-such-plugin")


def test_submit_calcjob_unknown_plugin():
    """Submitting to an uninstalled plugin is a ToolError."""
    with pytest.raises(ToolError, match="not installed"):
        calcjob.submit_calcjob("no-such-plugin", {})


def test_describe_unknown_workflow_is_tool_error():
    """Describing an uninstalled workflow is a ToolError."""
    with pytest.raises(ToolError, match="not installed"):
        workflow.describe_workflow("no-such-workflow")


def test_submit_workflow_unknown_plugin():
    """Submitting to an uninstalled workflow is a ToolError."""
    with pytest.raises(ToolError, match="not installed"):
        workflow.submit_workflow("no-such-workflow", {})


def test_register_all_registers_installed_plugins():
    """register_all registers tools for every installed plugin."""
    server = MCPServer("test")
    module, _ = fake_plugin_module()
    with mock.patch.object(
        plugins, "entry_points", return_value=[fake_entry_point("fake", module)]
    ):
        registered = plugins.register_all(server)

    assert "fake" in registered
    assert "fake_tool" in _tool_names(server)


def test_register_all_skips_plugin_that_is_not_installed():
    """register_all skips a plugin whose is_available() returns False."""
    server = MCPServer("test")
    module, _ = fake_plugin_module(available=False)
    with mock.patch.object(
        plugins, "entry_points", return_value=[fake_entry_point("fake", module)]
    ):
        registered = plugins.register_all(server)

    assert "fake" not in registered
    assert "fake_tool" not in _tool_names(server)


def test_register_all_registers_newly_available_plugin_on_rescan():
    """Calling register_all again after a plugin becomes available registers it."""
    server = MCPServer("test")
    module, state = fake_plugin_module(available=False)
    with mock.patch.object(
        plugins, "entry_points", return_value=[fake_entry_point("fake", module)]
    ):
        first = plugins.register_all(server)
        assert "fake" not in first

        state["available"] = True
        second = plugins.register_all(server)

    assert "fake" in second
    assert "fake_tool" in _tool_names(server)


def test_register_all_rescan_does_not_disturb_already_registered_tools():
    """Calling register_all again leaves already-registered tools untouched."""
    server = MCPServer("test")
    module, _ = fake_plugin_module()
    with mock.patch.object(
        plugins, "entry_points", return_value=[fake_entry_point("fake", module)]
    ):
        plugins.register_all(server)
        before = _tool_names(server)

        plugins.register_all(server)

    assert _tool_names(server) == before
    assert "fake_tool" in before


def test_entry_points_declare_bundled_plugins():
    """aiida-mcp's own pyproject.toml declares its bundled plugins' entry points."""
    names = {ep.name for ep in entry_points(group=plugins.ENTRY_POINT_GROUP)}
    assert names == {"mlip"}


def test_clear_entry_point_cache_clears_aiidas_cached_lookups():
    """clear_entry_point_cache clears AiiDA's cached entry point lookups."""
    with (
        mock.patch("aiida.plugins.entry_point.eps") as eps,
        mock.patch("aiida.plugins.entry_point.eps_select") as eps_select,
    ):
        plugins.clear_entry_point_cache()

    eps.cache_clear.assert_called_once()
    eps_select.cache_clear.assert_called_once()

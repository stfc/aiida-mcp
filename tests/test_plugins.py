"""Tests for the generic plugin registration and describe/submit helpers."""

import asyncio
from importlib.metadata import entry_points
from unittest import mock

import pytest
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from aiida_mcp import plugins
from aiida_mcp.plugins import calcjob, chemshell


def _tool_names(server: MCPServer) -> set[str]:
    return {tool.name for tool in asyncio.run(server.list_tools())}


def test_describe_chemshell_inputs():
    """describe_calcjob reports the ChemShell-specific inputs."""
    description = calcjob.describe_calcjob("chemshell")
    inputs = {port["name"]: port for port in description["inputs"]}

    assert inputs["structure"]["required"] is True
    assert inputs["structure"]["types"] == [
        "SinglefileData",
        "StructureData",
        "TrajectoryData",
    ]
    assert inputs["code"]["required"] is False


def test_describe_chemshell_outputs_exclude_base_calcjob_outputs():
    """describe_calcjob excludes outputs inherited from the base CalcJob."""
    description = calcjob.describe_calcjob("chemshell")
    outputs = {port["name"]: port for port in description["outputs"]}

    assert "energy" in outputs
    assert "optimised_structure" in outputs
    assert "retrieved" not in outputs


def test_describe_chemshell_exit_codes():
    """describe_calcjob reports the ChemShell-specific exit codes."""
    description = calcjob.describe_calcjob("chemshell")
    statuses = {code["status"]: code["name"] for code in description["exit_codes"]}

    assert statuses[300] == "ERROR_STDOUT_NOT_FOUND"


def test_describe_chemshell_option_defaults():
    """describe_calcjob reports the metadata option defaults the plugin changed."""
    defaults = calcjob.describe_calcjob("chemshell")["metadata_option_defaults"]

    assert defaults["parser_name"] == "chemshell"
    assert defaults["resources"] == {"num_machines": 1, "num_mpiprocs_per_machine": 4}


def test_chemshell_register_adds_tool():
    """register() adds the ChemShell describe and submit tools."""
    server = MCPServer("test")
    chemshell.register(server)
    assert _tool_names(server) == {
        "describe_chemshell_calcjob",
        "submit_chemshell_job",
    }


def test_describe_unknown_plugin_is_tool_error():
    """Describing an uninstalled plugin is a ToolError."""
    with pytest.raises(ToolError, match="not installed"):
        calcjob.describe_calcjob("no-such-plugin")


def test_submit_calcjob_unknown_plugin():
    """Submitting to an uninstalled plugin is a ToolError."""
    with pytest.raises(ToolError, match="not installed"):
        calcjob.submit_calcjob("no-such-plugin", {})


def test_register_all_registers_installed_plugins():
    """register_all registers tools for every installed plugin."""
    server = MCPServer("test")
    registered = plugins.register_all(server)

    assert "chemshell" in registered
    assert "describe_chemshell_calcjob" in _tool_names(server)


def test_register_all_skips_plugin_that_is_not_installed():
    """register_all skips a plugin whose is_available() returns False."""
    server = MCPServer("test")
    with mock.patch.object(chemshell, "is_available", return_value=False):
        registered = plugins.register_all(server)

    assert "chemshell" not in registered
    assert "describe_chemshell_calcjob" not in _tool_names(server)


def test_register_all_registers_newly_available_plugin_on_rescan():
    """Calling register_all again after a plugin becomes available registers it."""
    server = MCPServer("test")
    with mock.patch.object(chemshell, "is_available", return_value=False):
        first = plugins.register_all(server)
    assert "chemshell" not in first

    second = plugins.register_all(server)
    assert "chemshell" in second
    assert "describe_chemshell_calcjob" in _tool_names(server)


def test_register_all_rescan_does_not_disturb_already_registered_tools():
    """Calling register_all again leaves already-registered tools untouched."""
    server = MCPServer("test")
    plugins.register_all(server)
    before = _tool_names(server)

    plugins.register_all(server)

    assert _tool_names(server) == before


def test_entry_points_declare_bundled_plugins():
    """aiida-mcp's own pyproject.toml declares its bundled plugins' entry points."""
    names = {ep.name for ep in entry_points(group=plugins.ENTRY_POINT_GROUP)}
    assert names == {"chemshell", "mlip"}


def test_clear_entry_point_cache_clears_aiidas_cached_lookups():
    """clear_entry_point_cache clears AiiDA's cached entry point lookups."""
    with (
        mock.patch("aiida.plugins.entry_point.eps") as eps,
        mock.patch("aiida.plugins.entry_point.eps_select") as eps_select,
    ):
        plugins.clear_entry_point_cache()

    eps.cache_clear.assert_called_once()
    eps_select.cache_clear.assert_called_once()

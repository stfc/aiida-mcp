"""Tests for the generic plugin registration and describe/submit helpers."""

import asyncio
from importlib.metadata import entry_points
from unittest import mock

import pytest
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from aiida_mcp import plugins
from aiida_mcp.plugins import calcjob, chemshell, dlpoly


def _tool_names(server: MCPServer) -> set[str]:
    return {tool.name for tool in asyncio.run(server.list_tools())}


def test_describe_dlpoly_inputs():
    """describe_calcjob reports the DL_POLY-specific inputs."""
    description = calcjob.describe_calcjob("dlpoly")
    inputs = {port["name"]: port for port in description["inputs"]}

    assert set(inputs) == {"code", "configuration", "field", "control"}
    assert inputs["field"]["required"] is True
    assert inputs["field"]["types"] == ["SinglefileData"]
    assert inputs["control"]["types"] == ["SinglefileData", "Dict"]
    assert inputs["code"]["required"] is False


def test_describe_dlpoly_outputs_exclude_base_calcjob_outputs():
    """describe_calcjob excludes outputs inherited from the base CalcJob."""
    description = calcjob.describe_calcjob("dlpoly")
    outputs = {port["name"]: port for port in description["outputs"]}

    expected = {"output", "statistics", "revive_configuration", "rdf", "history"}
    assert set(outputs) == expected
    assert outputs["output"]["required"] is True
    assert outputs["rdf"]["required"] is False
    assert "retrieved" not in outputs


def test_describe_dlpoly_exit_codes():
    """describe_calcjob reports the DL_POLY-specific exit codes."""
    description = calcjob.describe_calcjob("dlpoly")
    statuses = {code["status"]: code["name"] for code in description["exit_codes"]}

    assert statuses[300] == "ERROR_OUTPUT_NOT_FOUND"
    assert sorted(statuses) == [300, 301, 302, 303, 304, 305]


def test_describe_dlpoly_option_defaults():
    """describe_calcjob reports the metadata option defaults the plugin changed."""
    defaults = calcjob.describe_calcjob("dlpoly")["metadata_option_defaults"]

    assert defaults["parser_name"] == "dlpoly"
    assert defaults["resources"] == {"num_machines": 1, "num_mpiprocs_per_machine": 1}


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


def test_dlpoly_register_adds_tool():
    """register() adds the DL_POLY describe and submit tools."""
    server = MCPServer("test")
    dlpoly.register(server)
    assert _tool_names(server) == {"describe_dlpoly_calcjob", "submit_dlpoly_job"}


def test_register_all_registers_installed_plugins():
    """register_all registers tools for every installed plugin."""
    server = MCPServer("test")
    registered = plugins.register_all(server)

    assert "dlpoly" in registered
    assert "describe_dlpoly_calcjob" in _tool_names(server)


def test_register_all_skips_plugin_that_is_not_installed():
    """register_all skips a plugin whose is_available() returns False."""
    server = MCPServer("test")
    with mock.patch.object(dlpoly, "is_available", return_value=False):
        registered = plugins.register_all(server)

    assert "dlpoly" not in registered
    assert "describe_dlpoly_calcjob" not in _tool_names(server)


def test_register_all_registers_newly_available_plugin_on_rescan():
    """Calling register_all again after a plugin becomes available registers it."""
    server = MCPServer("test")
    with mock.patch.object(dlpoly, "is_available", return_value=False):
        first = plugins.register_all(server)
    assert "dlpoly" not in first

    second = plugins.register_all(server)
    assert "dlpoly" in second
    assert "describe_dlpoly_calcjob" in _tool_names(server)


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
    assert names == {"dlpoly", "chemshell", "mlip"}


def test_clear_entry_point_cache_clears_aiidas_cached_lookups():
    """clear_entry_point_cache clears AiiDA's cached entry point lookups."""
    with (
        mock.patch("aiida.plugins.entry_point.eps") as eps,
        mock.patch("aiida.plugins.entry_point.eps_select") as eps_select,
    ):
        plugins.clear_entry_point_cache()

    eps.cache_clear.assert_called_once()
    eps_select.cache_clear.assert_called_once()

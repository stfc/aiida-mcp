import asyncio
from unittest import mock

import pytest
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from aiida_mcp import plugins
from aiida_mcp.plugins import calcjob, dlpoly


def _tool_names(server: MCPServer) -> set[str]:
    return {tool.name for tool in asyncio.run(server.list_tools())}


def test_describe_dlpoly_inputs():
    description = calcjob.describe_calcjob("dlpoly")
    inputs = {port["name"]: port for port in description["inputs"]}

    assert set(inputs) == {"code", "configuration", "field", "control"}
    assert inputs["field"]["required"] is True
    assert inputs["field"]["types"] == ["SinglefileData"]
    assert inputs["control"]["types"] == ["SinglefileData", "Dict"]
    assert inputs["code"]["required"] is False


def test_describe_dlpoly_outputs_exclude_base_calcjob_outputs():
    description = calcjob.describe_calcjob("dlpoly")
    outputs = {port["name"]: port for port in description["outputs"]}

    assert set(outputs) == {"output", "statistics", "revive_configuration", "rdf", "history"}
    assert outputs["output"]["required"] is True
    assert outputs["rdf"]["required"] is False
    assert "retrieved" not in outputs


def test_describe_dlpoly_exit_codes():
    description = calcjob.describe_calcjob("dlpoly")
    statuses = {code["status"]: code["name"] for code in description["exit_codes"]}

    assert statuses[300] == "ERROR_OUTPUT_NOT_FOUND"
    assert sorted(statuses) == [300, 301, 302, 303, 304, 305]


def test_describe_dlpoly_option_defaults():
    defaults = calcjob.describe_calcjob("dlpoly")["metadata_option_defaults"]

    assert defaults["parser_name"] == "dlpoly"
    assert defaults["resources"] == {"num_machines": 1, "num_mpiprocs_per_machine": 1}


def test_describe_unknown_plugin_is_tool_error():
    with pytest.raises(ToolError, match="not installed"):
        calcjob.describe_calcjob("no-such-plugin")


def test_dlpoly_register_adds_tool():
    server = MCPServer("test")
    dlpoly.register(server)
    assert _tool_names(server) == {"describe_dlpoly_calcjob", "submit_dlpoly_job"}


def test_register_all_registers_installed_plugins():
    server = MCPServer("test")
    registered = plugins.register_all(server)

    assert registered == ["aiida_mcp.plugins.dlpoly"]
    assert "describe_dlpoly_calcjob" in _tool_names(server)


def test_register_all_skips_plugin_that_is_not_installed():
    server = MCPServer("test")
    with mock.patch.object(dlpoly, "is_available", return_value=False):
        registered = plugins.register_all(server)

    assert registered == []
    assert _tool_names(server) == set()

"""Tests for the MCP server's tool registration and error handling."""

import asyncio

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from aiida_mcp import server


def test_all_tools_are_registered():
    """Every tool defined in server.py is exposed to MCP clients."""
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
        "describe_dlpoly_calcjob",
        "submit_dlpoly_job",
        "describe_chemshell_calcjob",
        "submit_chemshell_job",
        "describe_mlip_sp_calcjob",
        "describe_mlip_opt_calcjob",
        "describe_mlip_md_calcjob",
        "describe_mlip_ph_calcjob",
        "submit_mlip_sp_job",
        "submit_mlip_opt_job",
        "submit_mlip_md_job",
        "submit_mlip_ph_job",
    }


def test_tool_error_message_reaches_client():
    """A ToolError's message reaches the client without a traceback."""
    with pytest.raises(ToolError) as excinfo:
        asyncio.run(server.mcp.call_tool("get_process", {"pk": 999999}))
    assert "No node with pk 999999" in str(excinfo.value)
    assert "Traceback" not in str(excinfo.value)

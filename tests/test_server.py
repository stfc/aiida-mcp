import asyncio

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from aiida_mcp import server


def test_all_tools_are_registered():
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
    }


def test_tool_error_message_reaches_client():
    with pytest.raises(ToolError) as excinfo:
        asyncio.run(server.mcp.call_tool("get_process", {"pk": 999999}))
    assert "No node with pk 999999" in str(excinfo.value)
    assert "Traceback" not in str(excinfo.value)

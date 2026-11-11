import argparse

from mcp.server.mcpserver import MCPServer

from aiida_mcp import connection, nodes, plugins, processes

mcp = MCPServer("aiida-mcp")


@mcp.tool()
def ping() -> str:
    """Check that the server is running."""
    return "pong"


@mcp.tool()
def get_status() -> dict:
    """Report the AiiDA profile, daemon and broker status."""
    return connection.get_status()


@mcp.tool()
def list_processes(
    state: str | None = None,
    label: str | None = None,
    created_after: str | None = None,
    limit: int = 20,
) -> dict:
    """List AiiDA process nodes, newest first.

    state: one of created, waiting, running, finished, excepted, killed.
    label: exact process label to match.
    created_after: ISO date or datetime, e.g. 2026-11-01 or 2026-11-01T09:00:00.
    limit: maximum number of processes to return (capped at 200).
    """
    return processes.list_processes(state=state, label=label, created_after=created_after, limit=limit)


@mcp.tool()
def get_process(pk: int) -> dict:
    """Show details, inputs and outputs for one process node by PK."""
    return processes.get_process(pk)


@mcp.tool()
def get_process_report(pk: int, limit: int = 100) -> dict:
    """Show the most recent log messages for one process node by PK, oldest first.

    limit: maximum number of log entries to return (capped at 1000).
    """
    return processes.get_process_report(pk, limit=limit)


@mcp.tool()
def list_computers() -> dict:
    """List all configured computers."""
    return nodes.list_computers()


@mcp.tool()
def list_codes(computer: str | None = None, limit: int = 20) -> dict:
    """List codes, optionally only those on one computer.

    computer: computer label to filter by.
    limit: maximum number of codes to return (capped at 200).
    """
    return nodes.list_codes(computer=computer, limit=limit)


@mcp.tool()
def query_nodes(
    node_type: str | None = None,
    group: str | None = None,
    extra_key: str | None = None,
    limit: int = 20,
) -> dict:
    """Query nodes, newest first.

    node_type: node type prefix, e.g. data.core.int or process.calculation. A trailing % is optional.
    group: group label to restrict results to.
    extra_key: only nodes that have this extras key.
    limit: maximum number of nodes to return (capped at 200).
    """
    return nodes.query_nodes(node_type=node_type, group=group, extra_key=extra_key, limit=limit)


plugins.register_all(mcp)


def main() -> None:
    parser = argparse.ArgumentParser(description="AiiDA MCP server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http"],
        default="stdio",
        help="MCP transport to use (default: stdio)",
    )
    args = parser.parse_args()
    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()

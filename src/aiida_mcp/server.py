"""MCP server entry point and tool registration."""

import argparse

from mcp.server.mcpserver import MCPServer

from aiida_mcp import aiidalab, connection, nodes, plugins, processes, profiles

mcp = MCPServer("aiida-mcp")


@mcp.tool()
def ping() -> str:
    """Check that the server is running.

    Returns
    -------
    str
        Always ``"pong"``.
    """
    return "pong"


@mcp.tool()
def get_status() -> dict:
    """Report the AiiDA profile, daemon and broker status.

    Returns
    -------
    dict
        Whether a profile is loaded, the daemon state, and broker
        connectivity.
    """
    return connection.get_status()


@mcp.tool()
def list_processes(
    state: str | None = None,
    label: str | None = None,
    created_after: str | None = None,
    limit: int = 20,
) -> dict:
    """List AiiDA process nodes, newest first.

    Parameters
    ----------
    state : str or None
        One of created, waiting, running, finished, excepted, killed.
    label : str or None
        Exact process label to match.
    created_after : str or None
        ISO date or datetime, e.g. 2026-11-01 or 2026-11-01T09:00:00.
    limit : int
        Maximum number of processes to return (capped at 200).

    Returns
    -------
    dict
        The number of matching processes, the number returned, and a
        summary of each one.
    """
    return processes.list_processes(
        state=state, label=label, created_after=created_after, limit=limit
    )


@mcp.tool()
def get_process(pk: int) -> dict:
    """Show details, inputs and outputs for one process node by PK.

    Parameters
    ----------
    pk : int
        Primary key of the process node.

    Returns
    -------
    dict
        The process's details, plus summaries of its incoming and outgoing
        links.
    """
    return processes.get_process(pk)


@mcp.tool()
def get_process_report(pk: int, limit: int = 100) -> dict:
    """Show the most recent log messages for one process node by PK, oldest first.

    Parameters
    ----------
    pk : int
        Primary key of the process node.
    limit : int
        Maximum number of log entries to return (capped at 1000).

    Returns
    -------
    dict
        The total number of log entries, the number returned, and the log
        entries themselves.
    """
    return processes.get_process_report(pk, limit=limit)


@mcp.tool()
def list_computers() -> dict:
    """List all configured computers.

    Returns
    -------
    dict
        The total number of computers and a summary of each one.
    """
    return nodes.list_computers()


@mcp.tool()
def list_codes(computer: str | None = None, limit: int = 20) -> dict:
    """List codes, optionally only those on one computer.

    Parameters
    ----------
    computer : str or None
        Computer label to filter by.
    limit : int
        Maximum number of codes to return (capped at 200).

    Returns
    -------
    dict
        The number of matching codes, the number returned, and a summary of
        each one.
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

    Parameters
    ----------
    node_type : str or None
        Node type prefix, e.g. data.core.int or process.calculation. A
        trailing % is optional.
    group : str or None
        Group label to restrict results to.
    extra_key : str or None
        Only include nodes that have this extras key.
    limit : int
        Maximum number of nodes to return (capped at 200).

    Returns
    -------
    dict
        The number of matching nodes, the number returned, and a summary of
        each one.
    """
    return nodes.query_nodes(
        node_type=node_type, group=group, extra_key=extra_key, limit=limit
    )


@mcp.tool()
def get_node_content(pk: int) -> dict:
    """Return the content of a node, for node types where that is supported.

    Currently supported: SinglefileData (decoded as text when possible;
    content over 1 MB is truncated, and undecodable files are returned
    base64-encoded), Int and Float (returned as their numeric value).

    Parameters
    ----------
    pk : int
        Primary key of the node.

    Returns
    -------
    dict
        The node's content, in a shape that depends on its type.
    """
    return nodes.get_node_content(pk)


@mcp.tool()
def get_aiidalab_status() -> dict:
    """Report whether an AiiDAlab Jupyter server is running locally, and its URL.

    Looks for a running Jupyter server whose working directory looks like an
    AiiDAlab home directory. The returned URL includes the access token.

    Returns
    -------
    dict
        Whether a server is running and, if so, its URL, pid, root
        directory and version.
    """
    return aiidalab.get_status()


@mcp.tool()
def list_profiles() -> dict:
    """List all configured AiiDA profiles, showing the current and default ones.

    Returns
    -------
    dict
        The name of the currently loaded profile, the default profile, and
        a summary of every configured profile.
    """
    return profiles.list_profiles()


# create_profile and switch_profile are temporarily disabled. The underlying
# profiles.create_profile / profiles.switch_profile logic and tests are unchanged;
# re-enable by uncommenting these two tool registrations.
#
# @mcp.tool()
# def create_profile(
#     name: str,
#     email: str | None = None,
#     storage_backend: str = profiles.DEFAULT_STORAGE_BACKEND,
#     storage_config: dict | None = None,
#     broker: str = "none",
#     first_name: str | None = None,
#     last_name: str | None = None,
#     institution: str | None = None,
#     set_as_default: bool = False,
# ) -> dict:
#     """Create a new AiiDA profile and initialise its storage.
#
#     This does not switch the server's active profile; call switch_profile for that.
#
#     Parameters
#     ----------
#     name : str
#         Name for the new profile.
#     email : str or None
#         Default user's email. Required unless the storage backend is
#         read-only.
#     storage_backend : str
#         Storage entry point, e.g. core.sqlite_dos (default) or
#         core.psql_dos.
#     storage_config : dict or None
#         Backend-specific configuration, e.g. {"filepath": "/path/to/dir"}
#         for core.sqlite_dos, or database_username/database_password/
#         database_name/repository_uri for core.psql_dos. Unset fields fall
#         back to the defaults.
#     broker : str
#         Message broker to configure: none (default), core.rabbitmq or
#         core.zeromq.
#     first_name : str or None
#         First name for the default user.
#     last_name : str or None
#         Last name for the default user.
#     institution : str or None
#         Institution for the default user.
#     set_as_default : bool
#         Make this the default profile for future server starts.
#
#     Returns
#     -------
#     dict
#         The new profile's name, storage backend, broker backend, and
#         whether it is now the default.
#     """
#     return profiles.create_profile(
#         name=name,
#         email=email,
#         storage_backend=storage_backend,
#         storage_config=storage_config,
#         broker=broker,
#         first_name=first_name,
#         last_name=last_name,
#         institution=institution,
#         set_as_default=set_as_default,
#     )
#
#
# @mcp.tool()
# def switch_profile(name: str) -> dict:
#     """Switch the server's active AiiDA profile and initialise its storage.
#
#     Parameters
#     ----------
#     name : str
#         Name of an existing profile, as shown by list_profiles.
#
#     Returns
#     -------
#     dict
#         The result of list_profiles, reflecting the newly loaded profile.
#     """
#     return profiles.switch_profile(name)


plugins.register_all(mcp)


def main() -> None:
    """Parse command-line arguments and run the MCP server."""
    parser = argparse.ArgumentParser(description="AiiDA MCP server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http"],
        default="stdio",
        help="MCP transport to use (default: stdio)",
    )
    args = parser.parse_args()
    mcp.run(transport=args.transport, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()

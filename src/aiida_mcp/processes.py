from datetime import datetime
from typing import Any

from aiida import orm
from aiida.common import NotExistent, timezone
from mcp.server.mcpserver.exceptions import ToolError

from aiida_mcp import connection
from aiida_mcp.limits import clamp_limit

DEFAULT_LIMIT = 20
MAX_LIMIT = 200
DEFAULT_LOG_LIMIT = 100
MAX_LOG_LIMIT = 1000

PROCESS_STATES = ["created", "waiting", "running", "finished", "excepted", "killed"]


def _node_summary(node: orm.ProcessNode) -> dict[str, Any]:
    return {
        "pk": node.pk,
        "uuid": node.uuid,
        "label": node.process_label,
        "process_type": node.process_type,
        "state": node.process_state.value if node.process_state else None,
        "exit_status": node.exit_status,
        "ctime": node.ctime.isoformat(),
        "mtime": node.mtime.isoformat(),
    }


def list_processes(
    state: str | None = None,
    label: str | None = None,
    created_after: str | None = None,
    limit: int = DEFAULT_LIMIT,
) -> dict[str, Any]:
    """List process nodes, newest first, with optional filters."""
    connection.ensure_profile()

    if state is not None and state not in PROCESS_STATES:
        raise ToolError(f"Unknown state {state!r}. Choose from: {', '.join(PROCESS_STATES)}")

    filters: dict[str, Any] = {}
    if state is not None:
        filters["attributes.process_state"] = state
    if label is not None:
        filters["attributes.process_label"] = label
    if created_after is not None:
        filters["ctime"] = {">=": timezone.make_aware(datetime.fromisoformat(created_after))}

    limit = clamp_limit(limit, DEFAULT_LIMIT, MAX_LIMIT)

    qb = orm.QueryBuilder()
    qb.append(orm.ProcessNode, filters=filters, project=["*"])
    qb.order_by({orm.ProcessNode: {"ctime": "desc"}})
    total = qb.count()
    qb.limit(limit)

    processes = [_node_summary(node) for (node,) in qb.all()]
    return {
        "total_matching": total,
        "returned": len(processes),
        "processes": processes,
    }


def get_process(pk: int) -> dict[str, Any]:
    """Return details, inputs and outputs for one process node."""
    connection.ensure_profile()
    node = _load_process(pk)

    return {
        **_node_summary(node),
        "paused": node.paused,
        "inputs": _links_summary(node.base.links.get_incoming()),
        "outputs": _links_summary(node.base.links.get_outgoing()),
    }


def get_process_report(pk: int, limit: int = DEFAULT_LOG_LIMIT) -> dict[str, Any]:
    """Return the most recent log messages for one process node, oldest first."""
    connection.ensure_profile()
    node = _load_process(pk)
    limit = clamp_limit(limit, DEFAULT_LOG_LIMIT, MAX_LOG_LIMIT)

    logs = sorted(orm.Log.collection.get_logs_for(node), key=lambda log: log.time)
    total = len(logs)
    recent = logs[-limit:]

    return {
        "pk": node.pk,
        "total_logs": total,
        "returned": len(recent),
        "logs": [
            {
                "time": log.time.isoformat(),
                "level": log.levelname,
                "logger": log.loggername,
                "message": log.message,
            }
            for log in recent
        ],
    }


def _load_process(pk: int) -> orm.ProcessNode:
    try:
        node = orm.load_node(pk)
    except NotExistent as exc:
        raise ToolError(f"No node with pk {pk}") from exc
    if not isinstance(node, orm.ProcessNode):
        raise ToolError(f"Node {pk} is a {node.node_type}, not a process")
    return node


def _links_summary(triples) -> list[dict[str, Any]]:
    return [
        {
            "label": triple.link_label,
            "link_type": triple.link_type.value,
            "pk": triple.node.pk,
            "uuid": triple.node.uuid,
            "node_type": triple.node.node_type,
        }
        for triple in triples
    ]

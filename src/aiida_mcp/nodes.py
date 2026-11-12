import base64
from typing import Any

from aiida import orm
from aiida.common import NotExistent
from mcp.server.mcpserver.exceptions import ToolError

from aiida_mcp import connection
from aiida_mcp.limits import clamp_limit

DEFAULT_LIMIT = 20
MAX_LIMIT = 200
MAX_FILE_BYTES = 1_000_000


def _computer_summary(computer: orm.Computer) -> dict[str, Any]:
    return {
        "pk": computer.pk,
        "uuid": computer.uuid,
        "label": computer.label,
        "hostname": computer.hostname,
        "scheduler": computer.scheduler_type,
        "transport": computer.transport_type,
        "description": computer.description,
    }


def _code_summary(code: orm.InstalledCode | orm.PortableCode | orm.Code) -> dict[str, Any]:
    computer = code.computer
    return {
        "pk": code.pk,
        "uuid": code.uuid,
        "label": code.label,
        "description": code.description,
        "default_calc_job_plugin": code.default_calc_job_plugin,
        "computer": computer.label if computer is not None else None,
    }


def _node_summary(node: orm.Node) -> dict[str, Any]:
    return {
        "pk": node.pk,
        "uuid": node.uuid,
        "node_type": node.node_type,
        "label": node.label,
        "description": node.description,
        "ctime": node.ctime.isoformat(),
        "mtime": node.mtime.isoformat(),
    }


def list_computers() -> dict[str, Any]:
    """List all configured computers."""
    connection.ensure_profile()
    computers = orm.Computer.collection.all()
    return {
        "total": len(computers),
        "computers": [_computer_summary(computer) for computer in computers],
    }


def list_codes(computer: str | None = None, limit: int = DEFAULT_LIMIT) -> dict[str, Any]:
    """List codes, optionally only those on one computer."""
    connection.ensure_profile()
    limit = clamp_limit(limit, DEFAULT_LIMIT, MAX_LIMIT)

    qb = orm.QueryBuilder()
    qb.append(orm.Code, project=["*"])
    if computer is not None:
        qb.append(orm.Computer, filters={"label": computer}, with_node=orm.Code)
    total = qb.count()
    qb.limit(limit)

    return {
        "total_matching": total,
        "returned": min(total, limit),
        "codes": [_code_summary(code) for (code,) in qb.all()],
    }


def query_nodes(
    node_type: str | None = None,
    group: str | None = None,
    extra_key: str | None = None,
    limit: int = DEFAULT_LIMIT,
) -> dict[str, Any]:
    """Query nodes by type prefix, group label, and/or extras key."""
    connection.ensure_profile()
    limit = clamp_limit(limit, DEFAULT_LIMIT, MAX_LIMIT)

    filters: dict[str, Any] = {}
    if node_type is not None:
        filters["node_type"] = {"like": node_type if node_type.endswith("%") else f"{node_type}%"}
    if extra_key is not None:
        filters["extras"] = {"has_key": extra_key}

    qb = orm.QueryBuilder()
    qb.append(orm.Node, filters=filters, project=["*"])
    if group is not None:
        try:
            orm.load_group(label=group)
        except NotExistent as exc:
            raise ToolError(f"No group labelled {group!r}") from exc
        qb.append(orm.Group, filters={"label": group}, with_node=orm.Node)
    qb.order_by({orm.Node: {"ctime": "desc"}})
    total = qb.count()
    qb.limit(limit)

    return {
        "total_matching": total,
        "returned": min(total, limit),
        "nodes": [_node_summary(node) for (node,) in qb.all()],
    }


def get_node_content(pk: int) -> dict[str, Any]:
    """Return the content of a node, for node types where that is supported."""
    connection.ensure_profile()
    try:
        node = orm.load_node(pk)
    except NotExistent as exc:
        raise ToolError(f"No node with pk {pk}") from exc

    for node_cls, reader in _CONTENT_READERS.items():
        if isinstance(node, node_cls):
            return reader(node)

    supported = ", ".join(cls.__name__ for cls in _CONTENT_READERS)
    raise ToolError(
        f"Node {pk} is a {node.node_type}; reading content is only supported for: {supported}"
    )


def _singlefile_content(node: orm.SinglefileData) -> dict[str, Any]:
    with node.base.repository.open(node.filename, mode="rb") as handle:
        data = handle.read(MAX_FILE_BYTES + 1)
    truncated = len(data) > MAX_FILE_BYTES
    if truncated:
        data = data[:MAX_FILE_BYTES]

    try:
        content = data.decode("utf-8")
        encoding = "utf-8"
    except UnicodeDecodeError:
        content = base64.b64encode(data).decode("ascii")
        encoding = "base64"

    return {
        "pk": node.pk,
        "uuid": node.uuid,
        "node_type": node.node_type,
        "filename": node.filename,
        "encoding": encoding,
        "truncated": truncated,
        "content": content,
    }


def _value_content(node: orm.Int | orm.Float) -> dict[str, Any]:
    return {
        "pk": node.pk,
        "uuid": node.uuid,
        "node_type": node.node_type,
        "content": node.value,
    }


_CONTENT_READERS = {
    orm.SinglefileData: _singlefile_content,
    orm.Int: _value_content,
    orm.Float: _value_content,
}

from pathlib import Path
from typing import Any

from aiida import orm
from aiida.common import NotExistent
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import BaseModel, Field


class FileInput(BaseModel):
    """Where an input comes from. Give exactly one of path, text or pk."""

    path: str | None = Field(default=None, description="Path to a file on the machine running the server.")
    text: str | None = Field(default=None, description="The file contents as text.")
    pk: int | None = Field(default=None, description="PK of a node that is already stored in AiiDA.")


class ControlInput(FileInput):
    """A control input. Give exactly one of path, text, pk or parameters."""

    parameters: dict[str, Any] | None = Field(
        default=None, description="A dictionary of control parameters, stored as a Dict node."
    )


def build_node(
    source: FileInput,
    name: str,
    default_filename: str,
    accepted: tuple[type[orm.Node], ...],
) -> orm.Node:
    """Build an unstored node, or load a stored one, from a single input source."""
    given = {key: value for key, value in source.model_dump().items() if value is not None}
    if len(given) != 1:
        options = ", ".join(sorted(type(source).model_fields))
        raise ToolError(f"{name}: give exactly one of {options} (got {len(given)})")

    (kind, value), = given.items()

    if kind == "path":
        path = Path(value).expanduser()
        if not path.is_file():
            raise ToolError(f"{name}: no file at {str(path)!r}")
        return orm.SinglefileData(file=path, filename=path.name)

    if kind == "text":
        return orm.SinglefileData(content=value, filename=default_filename)

    if kind == "parameters":
        return orm.Dict(value)

    try:
        node = orm.load_node(value)
    except NotExistent as exc:
        raise ToolError(f"{name}: no node with pk {value}") from exc
    if not isinstance(node, accepted):
        expected = ", ".join(cls.__name__ for cls in accepted)
        raise ToolError(f"{name}: node {value} is a {type(node).__name__}, expected {expected}")
    return node

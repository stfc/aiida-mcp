"""Generic describe and submit helpers shared by workflow (WorkChain) plugins.

Unlike calcjobs, WorkChains commonly build their input namespace via
`spec.expose_inputs(...)` from other processes, producing deeply nested
`PortNamespace` inputs rather than a flat set of ports. Generically flattening
and describing that tree would be misleading (most of a WorkChain's real
inputs would appear as opaque, skipped namespaces), so `describe_workflow`
only reports outputs and exit codes, not inputs. A WorkChain's own
`submit_*` tool and its hand-written docstring are the authoritative
description of what it actually accepts to submit.

Some WorkChains (e.g. one that simply nests a calcjob's own inputs under one
extra namespace) still take inputs via a plain, JSON-shaped dict, just like a
calcjob's `submit_calcjob`; `submit_workflow` supports that case. Others build
their own `ProcessBuilder` via a bespoke `get_builder_from_protocol`-style
classmethod (e.g. one that orchestrates several other, heavier WorkChains);
there is no generic helper for that case — wrap the classmethod directly.
"""

from typing import Any

from aiida import orm
from aiida.engine import WorkChain, submit
from aiida.plugins import WorkflowFactory
from aiida.plugins.entry_point import get_entry_point_names
from mcp.server.mcpserver.exceptions import ToolError

ENTRY_POINT_GROUP = "aiida.workflows"


def workflow_available(entry_point: str) -> bool:
    """Return whether a workflow entry point is installed.

    Parameters
    ----------
    entry_point : str
        The workflow entry point name, e.g. ``cif2j.wannier_tb2j``.

    Returns
    -------
    bool
        True if the entry point is installed.
    """
    return entry_point in get_entry_point_names(ENTRY_POINT_GROUP)


def describe_workflow(entry_point: str) -> dict[str, Any]:
    """Describe the plugin-specific outputs and exit codes of a WorkChain.

    Outputs and exit codes inherited unchanged from the base `WorkChain` are left out.

    Parameters
    ----------
    entry_point : str
        The workflow entry point name, e.g. ``cif2j.wannier_tb2j``.

    Returns
    -------
    dict[str, Any]
        The workflow's entry point, class, description, plugin-specific
        outputs and exit codes.

    Raises
    ------
    ToolError
        If `entry_point` is not installed.
    """
    if not workflow_available(entry_point):
        raise ToolError(f"The workflow plugin {entry_point!r} is not installed")

    workflow = WorkflowFactory(entry_point)
    spec = workflow.spec()
    base = WorkChain.spec()

    return {
        "entry_point": entry_point,
        "class": f"{workflow.__module__}.{workflow.__name__}",
        "description": (workflow.__doc__ or "").strip(),
        "outputs": [
            _port_summary(name, port)
            for name, port in spec.outputs.items()
            if name not in base.outputs
        ],
        "exit_codes": [
            {"status": exit_code.status, "name": name, "message": exit_code.message}
            for name, exit_code in spec.exit_codes.items()
            if name not in base.exit_codes
        ],
    }


def submit_workflow(entry_point: str, inputs: dict[str, Any]) -> orm.ProcessNode:
    """Validate inputs against the workflow spec, store the data nodes and submit.

    Nothing is stored if validation fails. Inputs for an exposed namespace (e.g. from
    `spec.expose_inputs(OtherProcess, namespace="other")`) are given as a nested dict
    under that namespace's key, exactly as they would be passed to `submit`/`run`
    directly; any `orm.Data` values nested inside such a dict are stored too.

    Parameters
    ----------
    entry_point : str
        The workflow entry point name, e.g. ``chemshell.opt``.
    inputs : dict[str, Any]
        The workflow's inputs, including ``metadata`` (nested under any
        namespace that exposes it). Unstored `orm.Data` values, including
        ones nested inside namespace dicts, are stored before submission.

    Returns
    -------
    orm.ProcessNode
        The submitted process node.

    Raises
    ------
    ToolError
        If `entry_point` is not installed, or `inputs` fails validation.
    """
    if not workflow_available(entry_point):
        raise ToolError(f"The workflow plugin {entry_point!r} is not installed")

    workflow = WorkflowFactory(entry_point)
    error = workflow.spec().inputs.validate(inputs)
    if error is not None:
        raise ToolError(f"Invalid inputs for {entry_point}: {error}")

    for value in inputs.values():
        _store_unstored(value)

    return submit(workflow, **inputs)


def _store_unstored(value: Any) -> None:
    if isinstance(value, orm.Data):
        if not value.is_stored:
            value.store()
    elif isinstance(value, dict):
        for nested in value.values():
            _store_unstored(nested)


def _port_summary(name: str, port: Any) -> dict[str, Any]:
    return {
        "name": name,
        "required": bool(port.required),
        "types": _type_names(port.valid_type),
        "help": port.help or "",
    }


def _type_names(valid_type: Any) -> list[str]:
    types = valid_type if isinstance(valid_type, tuple) else (valid_type,)
    return [t.__name__ for t in types if t is not None and t is not type(None)]

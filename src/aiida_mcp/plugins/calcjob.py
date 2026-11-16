"""Generic describe and submit helpers shared by calcjob plugins."""

from typing import Any

from aiida import orm
from aiida.common import MultipleObjectsError, NotExistent
from aiida.engine import CalcJob, submit
from aiida.plugins import CalculationFactory
from aiida.plugins.entry_point import get_entry_point_names
from mcp.server.mcpserver.exceptions import ToolError
from plumpy.ports import PortNamespace

ENTRY_POINT_GROUP = "aiida.calculations"


def calcjob_available(entry_point: str) -> bool:
    """Return whether a calcjob entry point is installed.

    Parameters
    ----------
    entry_point : str
        The calcjob entry point name, e.g. ``dlpoly``.

    Returns
    -------
    bool
        True if the entry point is installed.
    """
    return entry_point in get_entry_point_names(ENTRY_POINT_GROUP)


def describe_calcjob(entry_point: str) -> dict[str, Any]:
    """Describe the plugin-specific inputs, outputs and exit codes of a calcjob.

    Ports and exit codes inherited unchanged from the base ``CalcJob`` are left out,
    except ``code``, which every calcjob needs.

    Parameters
    ----------
    entry_point : str
        The calcjob entry point name, e.g. ``dlpoly``.

    Returns
    -------
    dict[str, Any]
        The calcjob's entry point, class, description, plugin-specific
        inputs/outputs/exit codes, and changed metadata option defaults.

    Raises
    ------
    ToolError
        If `entry_point` is not installed.
    """
    if not calcjob_available(entry_point):
        raise ToolError(f"The calculation plugin {entry_point!r} is not installed")

    calcjob = CalculationFactory(entry_point)
    spec = calcjob.spec()
    base = CalcJob.spec()

    return {
        "entry_point": entry_point,
        "class": f"{calcjob.__module__}.{calcjob.__name__}",
        "description": (calcjob.__doc__ or "").strip(),
        "inputs": [
            _port_summary(name, port)
            for name, port in spec.inputs.items()
            if not isinstance(port, PortNamespace)
            and (name == "code" or name not in base.inputs)
        ],
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
        "metadata_option_defaults": _changed_option_defaults(spec, base),
    }


def submit_calcjob(entry_point: str, inputs: dict[str, Any]) -> orm.ProcessNode:
    """Validate inputs against the calcjob spec, store the data nodes and submit.

    Nothing is stored if validation fails.

    Parameters
    ----------
    entry_point : str
        The calcjob entry point name, e.g. ``dlpoly``.
    inputs : dict[str, Any]
        The calcjob's inputs, including ``metadata``. Unstored `orm.Data`
        values are stored before submission.

    Returns
    -------
    orm.ProcessNode
        The submitted process node.

    Raises
    ------
    ToolError
        If `entry_point` is not installed, or `inputs` fails validation.
    """
    if not calcjob_available(entry_point):
        raise ToolError(f"The calculation plugin {entry_point!r} is not installed")

    calcjob = CalculationFactory(entry_point)
    error = calcjob.spec().inputs.validate(inputs)
    if error is not None:
        raise ToolError(f"Invalid inputs for {entry_point}: {error}")

    for value in inputs.values():
        if isinstance(value, orm.Data) and not value.is_stored:
            value.store()

    return submit(calcjob, **inputs)


def load_code(identifier: str | int) -> orm.AbstractCode:
    """Load a code by label or PK, raising a ToolError if that fails.

    Parameters
    ----------
    identifier : str or int
        The code's full label (e.g. ``dl_poly@localhost``) or PK.

    Returns
    -------
    orm.AbstractCode
        The loaded code.

    Raises
    ------
    ToolError
        If no code matches `identifier`, or more than one does.
    """
    try:
        return orm.load_code(identifier)
    except NotExistent as exc:
        raise ToolError(f"No code found for {identifier!r}") from exc
    except MultipleObjectsError as exc:
        message = f"More than one code matches {identifier!r}, use its PK or full label"
        raise ToolError(message) from exc


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


def _changed_option_defaults(spec: Any, base: Any) -> dict[str, Any]:
    options = spec.inputs["metadata"]["options"]
    base_options = base.inputs["metadata"]["options"]

    changed = {}
    for name, port in options.items():
        if not port.has_default() or callable(port.default):
            continue
        base_port = base_options[name] if name in base_options else None
        if (
            base_port is not None
            and base_port.has_default()
            and base_port.default == port.default
        ):
            continue
        changed[name] = port.default
    return changed

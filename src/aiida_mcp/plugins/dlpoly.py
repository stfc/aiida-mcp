"""DL_POLY calcjob tools."""

from typing import Any

from aiida import orm
from aiida.engine.daemon.client import get_daemon_client
from aiida.manage.configuration import get_profile
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from aiida_mcp import connection
from aiida_mcp.plugins.calcjob import (
    calcjob_available,
    describe_calcjob,
    load_code,
    submit_calcjob,
)
from aiida_mcp.plugins.inputs import ControlInput, FileInput, build_node

ENTRY_POINT = "dlpoly"


def is_available() -> bool:
    """Return whether the DL_POLY calcjob plugin is installed."""
    return calcjob_available(ENTRY_POINT)


def submit_job(
    code: str | int,
    configuration: FileInput,
    field: FileInput,
    control: ControlInput,
    num_machines: int = 1,
    num_mpiprocs_per_machine: int = 1,
    label: str | None = None,
    description: str | None = None,
) -> dict[str, Any]:
    """Build the inputs for a DL_POLY calcjob and submit it to the daemon."""
    connection.ensure_profile()

    resources = (
        ("num_machines", num_machines),
        ("num_mpiprocs_per_machine", num_mpiprocs_per_machine),
    )
    for name, value in resources:
        if value < 1:
            raise ToolError(f"{name} must be at least 1, got {value}")

    metadata: dict[str, Any] = {
        "options": {
            "resources": {
                "num_machines": num_machines,
                "num_mpiprocs_per_machine": num_mpiprocs_per_machine,
            }
        }
    }
    if label is not None:
        metadata["label"] = label
    if description is not None:
        metadata["description"] = description

    inputs = {
        "code": load_code(code),
        "configuration": build_node(
            configuration,
            "configuration",
            "CONFIG",
            (orm.SinglefileData, orm.StructureData),
        ),
        "field": build_node(field, "field", "FIELD", (orm.SinglefileData,)),
        "control": build_node(
            control, "control", "CONTROL", (orm.SinglefileData, orm.Dict)
        ),
        "metadata": metadata,
    }

    node = submit_calcjob(ENTRY_POINT, inputs)

    daemon_running = get_daemon_client(get_profile().name).is_daemon_running
    result: dict[str, Any] = {
        "pk": node.pk,
        "uuid": node.uuid,
        "label": node.label,
        "description": node.description,
        "code": inputs["code"].full_label,
        "inputs": {
            name: inputs[name].pk for name in ("configuration", "field", "control")
        },
        "daemon_running": daemon_running,
    }
    if not daemon_running:
        result["note"] = "The daemon is not running; the job will wait until it starts."
    return result


def register(mcp: MCPServer) -> None:
    """Register the DL_POLY tools on the given MCP server."""

    @mcp.tool()
    def describe_dlpoly_calcjob() -> dict[str, Any]:
        """Describe the DL_POLY calcjob: inputs, outputs, exit codes and defaults."""
        return describe_calcjob(ENTRY_POINT)

    @mcp.tool()
    def submit_dlpoly_job(
        code: str | int,
        configuration: FileInput,
        field: FileInput,
        control: ControlInput,
        num_machines: int = 1,
        num_mpiprocs_per_machine: int = 1,
        label: str | None = None,
        description: str | None = None,
    ) -> dict[str, Any]:
        """Submit a DL_POLY calculation to the daemon; creates nodes and starts a job.

        code: label (e.g. dl_poly@localhost) or PK of the DL_POLY code.
        configuration: the CONFIG file, as a path, text, or PK of a SinglefileData or
            StructureData node.
        field: the FIELD file, as a path, text, or PK of a SinglefileData node.
        control: the CONTROL file as a path, text, or PK of a SinglefileData node, or a
            dict of parameters.
        num_machines: number of machines to run on.
        num_mpiprocs_per_machine: MPI processes per machine.
        label: optional label to set on the calcjob node.
        description: optional description to set on the calcjob node.

        Give exactly one of path, text, pk (or parameters for control) for each input.
        Returns the process PK. Follow the job with get_process and get_process_report.
        """
        return submit_job(
            code=code,
            configuration=configuration,
            field=field,
            control=control,
            num_machines=num_machines,
            num_mpiprocs_per_machine=num_mpiprocs_per_machine,
            label=label,
            description=description,
        )

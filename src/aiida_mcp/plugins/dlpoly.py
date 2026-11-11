from typing import Any

from aiida import orm
from aiida.common import MultipleObjectsError, NotExistent
from aiida.engine.daemon.client import get_daemon_client
from aiida.manage.configuration import get_profile
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from aiida_mcp import connection
from aiida_mcp.plugins.calcjob import calcjob_available, describe_calcjob, submit_calcjob
from aiida_mcp.plugins.inputs import ControlInput, FileInput, build_node

ENTRY_POINT = "dlpoly"


def is_available() -> bool:
    return calcjob_available(ENTRY_POINT)


def submit_job(
    code: str | int,
    configuration: FileInput,
    field: FileInput,
    control: ControlInput,
    num_machines: int = 1,
    num_mpiprocs_per_machine: int = 1,
) -> dict[str, Any]:
    """Build the inputs for a DL_POLY calcjob and submit it to the daemon."""
    connection.ensure_profile()

    for name, value in (("num_machines", num_machines), ("num_mpiprocs_per_machine", num_mpiprocs_per_machine)):
        if value < 1:
            raise ToolError(f"{name} must be at least 1, got {value}")

    inputs = {
        "code": _load_code(code),
        "configuration": build_node(
            configuration, "configuration", "CONFIG", (orm.SinglefileData, orm.StructureData)
        ),
        "field": build_node(field, "field", "FIELD", (orm.SinglefileData,)),
        "control": build_node(control, "control", "CONTROL", (orm.SinglefileData, orm.Dict)),
        "metadata": {
            "options": {
                "resources": {
                    "num_machines": num_machines,
                    "num_mpiprocs_per_machine": num_mpiprocs_per_machine,
                }
            }
        },
    }

    node = submit_calcjob(ENTRY_POINT, inputs)

    daemon_running = get_daemon_client(get_profile().name).is_daemon_running
    result: dict[str, Any] = {
        "pk": node.pk,
        "uuid": node.uuid,
        "code": inputs["code"].full_label,
        "inputs": {name: inputs[name].pk for name in ("configuration", "field", "control")},
        "daemon_running": daemon_running,
    }
    if not daemon_running:
        result["note"] = "The daemon is not running, so the job will wait until it is started."
    return result


def _load_code(identifier: str | int) -> orm.AbstractCode:
    try:
        return orm.load_code(identifier)
    except NotExistent as exc:
        raise ToolError(f"No code found for {identifier!r}") from exc
    except MultipleObjectsError as exc:
        raise ToolError(f"More than one code matches {identifier!r}, use its PK or full label") from exc


def register(mcp: MCPServer) -> None:
    @mcp.tool()
    def describe_dlpoly_calcjob() -> dict[str, Any]:
        """Describe the DL_POLY calcjob: its inputs, outputs, exit codes and default options."""
        return describe_calcjob(ENTRY_POINT)

    @mcp.tool()
    def submit_dlpoly_job(
        code: str | int,
        configuration: FileInput,
        field: FileInput,
        control: ControlInput,
        num_machines: int = 1,
        num_mpiprocs_per_machine: int = 1,
    ) -> dict[str, Any]:
        """Submit a DL_POLY calculation to the AiiDA daemon. This creates nodes and starts a job.

        code: label (e.g. dl_poly@localhost) or PK of the DL_POLY code.
        configuration: the CONFIG file, as a path, text, or PK of a SinglefileData or StructureData node.
        field: the FIELD file, as a path, text, or PK of a SinglefileData node.
        control: the CONTROL file as a path, text, or PK of a SinglefileData node, or a dict of parameters.
        num_machines: number of machines to run on.
        num_mpiprocs_per_machine: MPI processes per machine.

        Give exactly one of path, text, pk (or parameters for control) for each input.
        Returns the process PK. Use get_process and get_process_report to follow the job.
        """
        return submit_job(
            code=code,
            configuration=configuration,
            field=field,
            control=control,
            num_machines=num_machines,
            num_mpiprocs_per_machine=num_mpiprocs_per_machine,
        )

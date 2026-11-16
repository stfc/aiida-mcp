"""MLIP calcjob tools: single point, geometry optimisation, MD and phonons."""

from typing import Any

from aiida import orm
from aiida.common import NotExistent
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

ENTRY_POINTS = {
    "sp": "mlip.sp",
    "opt": "mlip.opt",
    "md": "mlip.md",
    "ph": "mlip.ph",
}


def is_available() -> bool:
    """Return whether the MLIP calcjob plugins are installed.

    Returns
    -------
    bool
        True if the ``mlip.sp`` entry point is installed.
    """
    return calcjob_available(ENTRY_POINTS["sp"])


def submit_sp_job(
    code: str | int,
    structure: str | int,
    model: str | int | None = None,
    architecture: str | None = None,
    device: str | None = None,
    calc_kwargs: dict[str, Any] | None = None,
    out: str | None = None,
    properties: list[str] | None = None,
    num_machines: int = 1,
    num_mpiprocs_per_machine: int = 1,
    label: str | None = None,
    description: str | None = None,
) -> dict[str, Any]:
    """Build the inputs for an MLIP single point calcjob and submit it.

    Parameters
    ----------
    code : str or int
        Label (e.g. ``janus@localhost``) or PK of the MLIP code.
    structure : str or int
        Path to a structure file on the machine running the server, or the
        PK of an existing `StructureData` node.
    model : str or int or None
        Path or URL of the MLIP model file, or the PK of an existing
        `ModelData` node. If omitted, the code's own default model for
        `architecture` is used.
    architecture : str or None
        MLIP architecture to use, e.g. ``mace_mp``. Required unless `model`
        is the PK of an existing `ModelData` node, which already carries
        its own architecture.
    device : str or None
        Device to run the calculation on: ``cpu``, ``cuda`` or ``mps``.
    calc_kwargs : dict or None
        Extra keyword arguments to pass to the selected calculator.
    out : str or None
        Name of the xyz output file.
    properties : list[str] or None
        Properties to calculate, e.g. ``["energy", "forces"]``.
    num_machines : int
        Number of machines to run on.
    num_mpiprocs_per_machine : int
        MPI processes per machine.
    label : str or None
        Optional label to set on the calcjob node.
    description : str or None
        Optional description to set on the calcjob node.

    Returns
    -------
    dict[str, Any]
        The process PK, uuid, label, description, code, input node PKs, and
        daemon state.

    Raises
    ------
    ToolError
        If `num_machines` or `num_mpiprocs_per_machine` is below 1, `code`,
        `structure` or `model` does not match a known code or node, or an
        input fails validation.
    """
    inputs = _common_inputs(
        code=code,
        structure=structure,
        model=model,
        architecture=architecture,
        device=device,
        calc_kwargs=calc_kwargs,
        num_machines=num_machines,
        num_mpiprocs_per_machine=num_mpiprocs_per_machine,
        label=label,
        description=description,
    )
    _set_scalar(inputs, "out", out, orm.Str)
    if properties is not None:
        inputs["properties"] = orm.List(properties)

    data_inputs = ("struct", "model", "out", "properties", "calc_kwargs")
    return _submit(ENTRY_POINTS["sp"], inputs, data_inputs)


def submit_opt_job(
    code: str | int,
    structure: str | int,
    model: str | int | None = None,
    architecture: str | None = None,
    device: str | None = None,
    calc_kwargs: dict[str, Any] | None = None,
    opt_cell_fully: bool | None = None,
    opt_cell_lengths: bool | None = None,
    fmax: float | None = None,
    steps: int | None = None,
    minimize_kwargs: dict[str, Any] | None = None,
    pressure: float | None = None,
    num_machines: int = 1,
    num_mpiprocs_per_machine: int = 1,
    label: str | None = None,
    description: str | None = None,
) -> dict[str, Any]:
    """Build the inputs for an MLIP geometry optimisation calcjob and submit it.

    Parameters
    ----------
    code : str or int
        Label (e.g. ``janus@localhost``) or PK of the MLIP code.
    structure : str or int
        Path to a structure file on the machine running the server, or the
        PK of an existing `StructureData` node.
    model : str or int or None
        Path or URL of the MLIP model file, or the PK of an existing
        `ModelData` node. If omitted, the code's own default model for
        `architecture` is used.
    architecture : str or None
        MLIP architecture to use, e.g. ``mace_mp``. Required unless `model`
        is the PK of an existing `ModelData` node, which already carries
        its own architecture.
    device : str or None
        Device to run the calculation on: ``cpu``, ``cuda`` or ``mps``.
    calc_kwargs : dict or None
        Extra keyword arguments to pass to the selected calculator.
    opt_cell_fully : bool or None
        Fully optimise the cell vectors, angles, and atomic positions.
    opt_cell_lengths : bool or None
        Optimise cell vectors, as well as atomic positions.
    fmax : float or None
        Maximum force for convergence.
    steps : int or None
        Number of optimisation steps.
    minimize_kwargs : dict or None
        All other keyword arguments to pass to the geometry optimizer.
    pressure : float or None
        Scalar pressure when optimizing cell geometry, in GPa.
    num_machines : int
        Number of machines to run on.
    num_mpiprocs_per_machine : int
        MPI processes per machine.
    label : str or None
        Optional label to set on the calcjob node.
    description : str or None
        Optional description to set on the calcjob node.

    Returns
    -------
    dict[str, Any]
        The process PK, uuid, label, description, code, input node PKs, and
        daemon state.

    Raises
    ------
    ToolError
        If `num_machines` or `num_mpiprocs_per_machine` is below 1, `code`,
        `structure` or `model` does not match a known code or node, or an
        input fails validation.
    """
    inputs = _common_inputs(
        code=code,
        structure=structure,
        model=model,
        architecture=architecture,
        device=device,
        calc_kwargs=calc_kwargs,
        num_machines=num_machines,
        num_mpiprocs_per_machine=num_mpiprocs_per_machine,
        label=label,
        description=description,
    )
    _set_scalar(inputs, "opt_cell_fully", opt_cell_fully, orm.Bool)
    _set_scalar(inputs, "opt_cell_lengths", opt_cell_lengths, orm.Bool)
    _set_scalar(inputs, "fmax", fmax, orm.Float)
    _set_scalar(inputs, "steps", steps, orm.Int)
    _set_scalar(inputs, "pressure", pressure, orm.Float)
    if minimize_kwargs is not None:
        inputs["minimize_kwargs"] = orm.Dict(minimize_kwargs)

    data_inputs = (
        "struct",
        "model",
        "opt_cell_fully",
        "opt_cell_lengths",
        "fmax",
        "steps",
        "minimize_kwargs",
        "pressure",
        "calc_kwargs",
    )
    return _submit(ENTRY_POINTS["opt"], inputs, data_inputs)


def submit_md_job(
    code: str | int,
    structure: str | int,
    model: str | int | None = None,
    architecture: str | None = None,
    device: str | None = None,
    calc_kwargs: dict[str, Any] | None = None,
    ensemble: str | None = None,
    md_kwargs: dict[str, Any] | None = None,
    num_machines: int = 1,
    num_mpiprocs_per_machine: int = 1,
    label: str | None = None,
    description: str | None = None,
) -> dict[str, Any]:
    """Build the inputs for an MLIP molecular dynamics calcjob and submit it.

    Parameters
    ----------
    code : str or int
        Label (e.g. ``janus@localhost``) or PK of the MLIP code.
    structure : str or int
        Path to a structure file on the machine running the server, or the
        PK of an existing `StructureData` node.
    model : str or int or None
        Path or URL of the MLIP model file, or the PK of an existing
        `ModelData` node. If omitted, the code's own default model for
        `architecture` is used.
    architecture : str or None
        MLIP architecture to use, e.g. ``mace_mp``. Required unless `model`
        is the PK of an existing `ModelData` node, which already carries
        its own architecture.
    device : str or None
        Device to run the calculation on: ``cpu``, ``cuda`` or ``mps``.
    calc_kwargs : dict or None
        Extra keyword arguments to pass to the selected calculator.
    ensemble : str or None
        Name of the thermodynamic ensemble.
    md_kwargs : dict or None
        Keyword arguments for the molecular dynamics run.
    num_machines : int
        Number of machines to run on.
    num_mpiprocs_per_machine : int
        MPI processes per machine.
    label : str or None
        Optional label to set on the calcjob node.
    description : str or None
        Optional description to set on the calcjob node.

    Returns
    -------
    dict[str, Any]
        The process PK, uuid, label, description, code, input node PKs, and
        daemon state.

    Raises
    ------
    ToolError
        If `num_machines` or `num_mpiprocs_per_machine` is below 1, `code`,
        `structure` or `model` does not match a known code or node, or an
        input fails validation.
    """
    inputs = _common_inputs(
        code=code,
        structure=structure,
        model=model,
        architecture=architecture,
        device=device,
        calc_kwargs=calc_kwargs,
        num_machines=num_machines,
        num_mpiprocs_per_machine=num_mpiprocs_per_machine,
        label=label,
        description=description,
    )
    _set_scalar(inputs, "ensemble", ensemble, orm.Str)
    if md_kwargs is not None:
        inputs["md_kwargs"] = orm.Dict(md_kwargs)

    data_inputs = ("struct", "model", "ensemble", "md_kwargs", "calc_kwargs")
    return _submit(ENTRY_POINTS["md"], inputs, data_inputs)


def submit_ph_job(
    code: str | int,
    structure: str | int,
    model: str | int | None = None,
    architecture: str | None = None,
    device: str | None = None,
    calc_kwargs: dict[str, Any] | None = None,
    out: str | None = None,
    supercell: str | None = None,
    n_qpoints: int | None = None,
    displacement: float | None = None,
    no_hdf5: bool | None = None,
    dos: bool | None = None,
    pdos: bool | None = None,
    bands: bool | None = None,
    symmetrize: bool | None = None,
    qpoint_file: str | None = None,
    num_machines: int = 1,
    num_mpiprocs_per_machine: int = 1,
    label: str | None = None,
    description: str | None = None,
) -> dict[str, Any]:
    """Build the inputs for an MLIP phonon calcjob and submit it.

    Parameters
    ----------
    code : str or int
        Label (e.g. ``janus@localhost``) or PK of the MLIP code.
    structure : str or int
        Path to a structure file on the machine running the server, or the
        PK of an existing `StructureData` node.
    model : str or int or None
        Path or URL of the MLIP model file, or the PK of an existing
        `ModelData` node. If omitted, the code's own default model for
        `architecture` is used.
    architecture : str or None
        MLIP architecture to use, e.g. ``mace_mp``. Required unless `model`
        is the PK of an existing `ModelData` node, which already carries
        its own architecture.
    device : str or None
        Device to run the calculation on: ``cpu``, ``cuda`` or ``mps``.
    calc_kwargs : dict or None
        Extra keyword arguments to pass to the selected calculator.
    out : str or None
        Name of the phonon output file.
    supercell : str or None
        The size of supercells used in the phonon calculation.
    n_qpoints : int or None
        Number of q points in the band path.
    displacement : float or None
        Displacement for numerical derivatives.
    no_hdf5 : bool or None
        Write force constants to the phonopy yaml, rather than separate
        HDF5.
    dos : bool or None
        Calculate the density of states.
    pdos : bool or None
        Calculate the partial density of states.
    bands : bool or None
        Calculate the phonon band structure.
    symmetrize : bool or None
        Symmetrize force constants.
    qpoint_file : str or None
        The file for q-points in the phonon calculation.
    num_machines : int
        Number of machines to run on.
    num_mpiprocs_per_machine : int
        MPI processes per machine.
    label : str or None
        Optional label to set on the calcjob node.
    description : str or None
        Optional description to set on the calcjob node.

    Returns
    -------
    dict[str, Any]
        The process PK, uuid, label, description, code, input node PKs, and
        daemon state.

    Raises
    ------
    ToolError
        If `num_machines` or `num_mpiprocs_per_machine` is below 1, `code`,
        `structure` or `model` does not match a known code or node, or an
        input fails validation.
    """
    inputs = _common_inputs(
        code=code,
        structure=structure,
        model=model,
        architecture=architecture,
        device=device,
        calc_kwargs=calc_kwargs,
        num_machines=num_machines,
        num_mpiprocs_per_machine=num_mpiprocs_per_machine,
        label=label,
        description=description,
    )
    _set_scalar(inputs, "out", out, orm.Str)
    _set_scalar(inputs, "supercell", supercell, orm.Str)
    _set_scalar(inputs, "n_qpoints", n_qpoints, orm.Int)
    _set_scalar(inputs, "displacement", displacement, orm.Float)
    _set_scalar(inputs, "no_hdf5", no_hdf5, orm.Bool)
    _set_scalar(inputs, "dos", dos, orm.Bool)
    _set_scalar(inputs, "pdos", pdos, orm.Bool)
    _set_scalar(inputs, "bands", bands, orm.Bool)
    _set_scalar(inputs, "symmetrize", symmetrize, orm.Bool)
    _set_scalar(inputs, "qpoint_file", qpoint_file, orm.Str)

    data_inputs = (
        "struct",
        "model",
        "out",
        "supercell",
        "n_qpoints",
        "displacement",
        "no_hdf5",
        "dos",
        "pdos",
        "bands",
        "symmetrize",
        "qpoint_file",
        "calc_kwargs",
    )
    return _submit(ENTRY_POINTS["ph"], inputs, data_inputs)


def _common_inputs(
    code: str | int,
    structure: str | int,
    model: str | int | None,
    architecture: str | None,
    device: str | None,
    calc_kwargs: dict[str, Any] | None,
    num_machines: int,
    num_mpiprocs_per_machine: int,
    label: str | None,
    description: str | None,
) -> dict[str, Any]:
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

    inputs: dict[str, Any] = {
        "code": load_code(code),
        "struct": _load_structure(structure),
        "metadata": metadata,
    }
    model_node = _load_model(model, architecture)
    if model_node is not None:
        inputs["model"] = model_node
    elif architecture is not None:
        inputs["arch"] = orm.Str(architecture)
    _set_scalar(inputs, "device", device, orm.Str)
    if calc_kwargs is not None:
        inputs["calc_kwargs"] = orm.Dict(calc_kwargs)
    return inputs


def _load_structure(structure: str | int) -> orm.StructureData:
    from aiida_mlip.helpers.help_load import load_structure

    try:
        return load_structure(structure)
    except Exception as exc:
        raise ToolError(f"structure: {exc}") from exc


def _load_model(model: str | int | None, architecture: str | None) -> orm.Data | None:
    if model is None:
        return None

    if isinstance(model, int):
        from aiida_mlip.data.model import ModelData

        try:
            node = orm.load_node(model)
        except NotExistent as exc:
            raise ToolError(f"model: no node with pk {model}") from exc
        if not isinstance(node, ModelData):
            got = type(node).__name__
            raise ToolError(f"model: node {model} is a {got}, expected ModelData")
        return node

    if architecture is None:
        raise ToolError("architecture is required when model is a path or URL")

    from aiida_mlip.helpers.help_load import load_model

    try:
        return load_model(model, architecture)
    except Exception as exc:
        raise ToolError(f"model: {exc}") from exc


def _set_scalar(
    inputs: dict[str, Any], name: str, value: Any, wrapper: type[orm.Data]
) -> None:
    if value is not None:
        inputs[name] = wrapper(value)


def _submit(
    entry_point: str, inputs: dict[str, Any], data_input_names: tuple[str, ...]
) -> dict[str, Any]:
    node = submit_calcjob(entry_point, inputs)

    daemon_running = get_daemon_client(get_profile().name).is_daemon_running
    data_inputs = {name: inputs[name].pk for name in data_input_names if name in inputs}
    result: dict[str, Any] = {
        "pk": node.pk,
        "uuid": node.uuid,
        "label": node.label,
        "description": node.description,
        "code": inputs["code"].full_label,
        "inputs": data_inputs,
        "daemon_running": daemon_running,
    }
    if not daemon_running:
        result["note"] = "The daemon is not running; the job will wait until it starts."
    return result


def register(mcp: MCPServer) -> None:
    """Register the MLIP tools on the given MCP server.

    Parameters
    ----------
    mcp : MCPServer
        The server to register the MLIP tools on.
    """

    @mcp.tool()
    def describe_mlip_sp_calcjob() -> dict[str, Any]:
        """Describe the MLIP single point calcjob.

        Returns
        -------
        dict[str, Any]
            The calcjob's inputs, outputs, exit codes and changed metadata
            option defaults.
        """
        return describe_calcjob(ENTRY_POINTS["sp"])

    @mcp.tool()
    def describe_mlip_opt_calcjob() -> dict[str, Any]:
        """Describe the MLIP geometry optimisation calcjob.

        Returns
        -------
        dict[str, Any]
            The calcjob's inputs, outputs, exit codes and changed metadata
            option defaults.
        """
        return describe_calcjob(ENTRY_POINTS["opt"])

    @mcp.tool()
    def describe_mlip_md_calcjob() -> dict[str, Any]:
        """Describe the MLIP molecular dynamics calcjob.

        Returns
        -------
        dict[str, Any]
            The calcjob's inputs, outputs, exit codes and changed metadata
            option defaults.
        """
        return describe_calcjob(ENTRY_POINTS["md"])

    @mcp.tool()
    def describe_mlip_ph_calcjob() -> dict[str, Any]:
        """Describe the MLIP phonon calcjob.

        Returns
        -------
        dict[str, Any]
            The calcjob's inputs, outputs, exit codes and changed metadata
            option defaults.
        """
        return describe_calcjob(ENTRY_POINTS["ph"])

    @mcp.tool()
    def submit_mlip_sp_job(
        code: str | int,
        structure: str | int,
        model: str | int | None = None,
        architecture: str | None = None,
        device: str | None = None,
        calc_kwargs: dict[str, Any] | None = None,
        out: str | None = None,
        properties: list[str] | None = None,
        num_machines: int = 1,
        num_mpiprocs_per_machine: int = 1,
        label: str | None = None,
        description: str | None = None,
    ) -> dict[str, Any]:
        """Submit an MLIP single point calculation to the daemon.

        Creates nodes and starts a job. Follow it with `get_process` and
        `get_process_report`.

        Parameters
        ----------
        code : str or int
            Label (e.g. ``janus@localhost``) or PK of the MLIP code.
        structure : str or int
            Path to a structure file on the machine running the server, or
            the PK of an existing StructureData node.
        model : str or int or None
            Path or URL of the MLIP model file, or the PK of an existing
            ModelData node. If omitted, the code's own default model for
            `architecture` is used.
        architecture : str or None
            MLIP architecture to use, e.g. ``mace_mp``. Required unless
            `model` is the PK of an existing ModelData node.
        device : str or None
            Device to run the calculation on: cpu, cuda or mps.
        calc_kwargs : dict or None
            Extra keyword arguments to pass to the selected calculator.
        out : str or None
            Name of the xyz output file.
        properties : list[str] or None
            Properties to calculate, e.g. ["energy", "forces"].
        num_machines : int
            Number of machines to run on.
        num_mpiprocs_per_machine : int
            MPI processes per machine.
        label : str or None
            Optional label to set on the calcjob node.
        description : str or None
            Optional description to set on the calcjob node.

        Returns
        -------
        dict[str, Any]
            The process PK, uuid, label, description, code, input node PKs,
            and daemon state.
        """
        return submit_sp_job(
            code=code,
            structure=structure,
            model=model,
            architecture=architecture,
            device=device,
            calc_kwargs=calc_kwargs,
            out=out,
            properties=properties,
            num_machines=num_machines,
            num_mpiprocs_per_machine=num_mpiprocs_per_machine,
            label=label,
            description=description,
        )

    @mcp.tool()
    def submit_mlip_opt_job(
        code: str | int,
        structure: str | int,
        model: str | int | None = None,
        architecture: str | None = None,
        device: str | None = None,
        calc_kwargs: dict[str, Any] | None = None,
        opt_cell_fully: bool | None = None,
        opt_cell_lengths: bool | None = None,
        fmax: float | None = None,
        steps: int | None = None,
        minimize_kwargs: dict[str, Any] | None = None,
        pressure: float | None = None,
        num_machines: int = 1,
        num_mpiprocs_per_machine: int = 1,
        label: str | None = None,
        description: str | None = None,
    ) -> dict[str, Any]:
        """Submit an MLIP geometry optimisation to the daemon.

        Creates nodes and starts a job. Follow it with `get_process` and
        `get_process_report`.

        Parameters
        ----------
        code : str or int
            Label (e.g. ``janus@localhost``) or PK of the MLIP code.
        structure : str or int
            Path to a structure file on the machine running the server, or
            the PK of an existing StructureData node.
        model : str or int or None
            Path or URL of the MLIP model file, or the PK of an existing
            ModelData node. If omitted, the code's own default model for
            `architecture` is used.
        architecture : str or None
            MLIP architecture to use, e.g. ``mace_mp``. Required unless
            `model` is the PK of an existing ModelData node.
        device : str or None
            Device to run the calculation on: cpu, cuda or mps.
        calc_kwargs : dict or None
            Extra keyword arguments to pass to the selected calculator.
        opt_cell_fully : bool or None
            Fully optimise the cell vectors, angles, and atomic positions.
        opt_cell_lengths : bool or None
            Optimise cell vectors, as well as atomic positions.
        fmax : float or None
            Maximum force for convergence.
        steps : int or None
            Number of optimisation steps.
        minimize_kwargs : dict or None
            All other keyword arguments to pass to the geometry optimizer.
        pressure : float or None
            Scalar pressure when optimizing cell geometry, in GPa.
        num_machines : int
            Number of machines to run on.
        num_mpiprocs_per_machine : int
            MPI processes per machine.
        label : str or None
            Optional label to set on the calcjob node.
        description : str or None
            Optional description to set on the calcjob node.

        Returns
        -------
        dict[str, Any]
            The process PK, uuid, label, description, code, input node PKs,
            and daemon state.
        """
        return submit_opt_job(
            code=code,
            structure=structure,
            model=model,
            architecture=architecture,
            device=device,
            calc_kwargs=calc_kwargs,
            opt_cell_fully=opt_cell_fully,
            opt_cell_lengths=opt_cell_lengths,
            fmax=fmax,
            steps=steps,
            minimize_kwargs=minimize_kwargs,
            pressure=pressure,
            num_machines=num_machines,
            num_mpiprocs_per_machine=num_mpiprocs_per_machine,
            label=label,
            description=description,
        )

    @mcp.tool()
    def submit_mlip_md_job(
        code: str | int,
        structure: str | int,
        model: str | int | None = None,
        architecture: str | None = None,
        device: str | None = None,
        calc_kwargs: dict[str, Any] | None = None,
        ensemble: str | None = None,
        md_kwargs: dict[str, Any] | None = None,
        num_machines: int = 1,
        num_mpiprocs_per_machine: int = 1,
        label: str | None = None,
        description: str | None = None,
    ) -> dict[str, Any]:
        """Submit an MLIP molecular dynamics run to the daemon.

        Creates nodes and starts a job. Follow it with `get_process` and
        `get_process_report`.

        Parameters
        ----------
        code : str or int
            Label (e.g. ``janus@localhost``) or PK of the MLIP code.
        structure : str or int
            Path to a structure file on the machine running the server, or
            the PK of an existing StructureData node.
        model : str or int or None
            Path or URL of the MLIP model file, or the PK of an existing
            ModelData node. If omitted, the code's own default model for
            `architecture` is used.
        architecture : str or None
            MLIP architecture to use, e.g. ``mace_mp``. Required unless
            `model` is the PK of an existing ModelData node.
        device : str or None
            Device to run the calculation on: cpu, cuda or mps.
        calc_kwargs : dict or None
            Extra keyword arguments to pass to the selected calculator.
        ensemble : str or None
            Name of the thermodynamic ensemble.
        md_kwargs : dict or None
            Keyword arguments for the molecular dynamics run.
        num_machines : int
            Number of machines to run on.
        num_mpiprocs_per_machine : int
            MPI processes per machine.
        label : str or None
            Optional label to set on the calcjob node.
        description : str or None
            Optional description to set on the calcjob node.

        Returns
        -------
        dict[str, Any]
            The process PK, uuid, label, description, code, input node PKs,
            and daemon state.
        """
        return submit_md_job(
            code=code,
            structure=structure,
            model=model,
            architecture=architecture,
            device=device,
            calc_kwargs=calc_kwargs,
            ensemble=ensemble,
            md_kwargs=md_kwargs,
            num_machines=num_machines,
            num_mpiprocs_per_machine=num_mpiprocs_per_machine,
            label=label,
            description=description,
        )

    @mcp.tool()
    def submit_mlip_ph_job(
        code: str | int,
        structure: str | int,
        model: str | int | None = None,
        architecture: str | None = None,
        device: str | None = None,
        calc_kwargs: dict[str, Any] | None = None,
        out: str | None = None,
        supercell: str | None = None,
        n_qpoints: int | None = None,
        displacement: float | None = None,
        no_hdf5: bool | None = None,
        dos: bool | None = None,
        pdos: bool | None = None,
        bands: bool | None = None,
        symmetrize: bool | None = None,
        qpoint_file: str | None = None,
        num_machines: int = 1,
        num_mpiprocs_per_machine: int = 1,
        label: str | None = None,
        description: str | None = None,
    ) -> dict[str, Any]:
        """Submit an MLIP phonon calculation to the daemon.

        Creates nodes and starts a job. Follow it with `get_process` and
        `get_process_report`.

        Parameters
        ----------
        code : str or int
            Label (e.g. ``janus@localhost``) or PK of the MLIP code.
        structure : str or int
            Path to a structure file on the machine running the server, or
            the PK of an existing StructureData node.
        model : str or int or None
            Path or URL of the MLIP model file, or the PK of an existing
            ModelData node. If omitted, the code's own default model for
            `architecture` is used.
        architecture : str or None
            MLIP architecture to use, e.g. ``mace_mp``. Required unless
            `model` is the PK of an existing ModelData node.
        device : str or None
            Device to run the calculation on: cpu, cuda or mps.
        calc_kwargs : dict or None
            Extra keyword arguments to pass to the selected calculator.
        out : str or None
            Name of the phonon output file.
        supercell : str or None
            The size of supercells used in the phonon calculation.
        n_qpoints : int or None
            Number of q points in the band path.
        displacement : float or None
            Displacement for numerical derivatives.
        no_hdf5 : bool or None
            Write force constants to the phonopy yaml, rather than separate
            HDF5.
        dos : bool or None
            Calculate the density of states.
        pdos : bool or None
            Calculate the partial density of states.
        bands : bool or None
            Calculate the phonon band structure.
        symmetrize : bool or None
            Symmetrize force constants.
        qpoint_file : str or None
            The file for q-points in the phonon calculation.
        num_machines : int
            Number of machines to run on.
        num_mpiprocs_per_machine : int
            MPI processes per machine.
        label : str or None
            Optional label to set on the calcjob node.
        description : str or None
            Optional description to set on the calcjob node.

        Returns
        -------
        dict[str, Any]
            The process PK, uuid, label, description, code, input node PKs,
            and daemon state.
        """
        return submit_ph_job(
            code=code,
            structure=structure,
            model=model,
            architecture=architecture,
            device=device,
            calc_kwargs=calc_kwargs,
            out=out,
            supercell=supercell,
            n_qpoints=n_qpoints,
            displacement=displacement,
            no_hdf5=no_hdf5,
            dos=dos,
            pdos=pdos,
            bands=bands,
            symmetrize=symmetrize,
            qpoint_file=qpoint_file,
            num_machines=num_machines,
            num_mpiprocs_per_machine=num_mpiprocs_per_machine,
            label=label,
            description=description,
        )

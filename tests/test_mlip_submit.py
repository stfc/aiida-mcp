"""Tests for building MLIP input nodes and submitting MLIP calcjobs.

aiida-mlip is not installed in this environment, so these tests inject
minimal fake ``aiida_mlip`` modules via ``sys.modules`` that mimic the real
package's public API (``helpers.help_load.load_structure``/``load_model``
and ``data.model.ModelData``). This exercises `aiida_mcp.plugins.mlip`'s own
glue logic, not the real package's behaviour.
"""

import asyncio
import sys
import types
import uuid
from unittest import mock

import pytest
from aiida import orm
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from aiida_mcp.plugins import mlip

# The real mlip.* entry points are not registered in this environment (aiida-mlip
# is not installed), so submit_calcjob itself is replaced rather than the
# lower-level aiida.engine.submit it would normally call. This bypasses real
# calcjob spec validation.


@pytest.fixture
def code(aiida_localhost):
    """Return a stored MLIP code on the test computer."""
    return orm.InstalledCode(
        label=f"mlip-test-{uuid.uuid4().hex[:8]}",
        computer=aiida_localhost,
        filepath_executable="/bin/true",
        default_calc_job_plugin="mlip.sp",
    ).store()


@pytest.fixture
def fake_submit(monkeypatch):
    """Replace submit_calcjob with a stub that returns a process-like node."""
    node = orm.CalcJobNode()
    node.set_process_type("aiida.calculations:mlip.sp")
    node.store_all = lambda: None
    stub = mock.Mock(return_value=node)
    monkeypatch.setattr(mlip, "submit_calcjob", stub)
    return stub


@pytest.fixture
def stored_node_returned(fake_submit):
    """Make the fake submit return an already-stored CalcJobNode."""
    fake_submit.return_value = orm.CalcJobNode().store()
    return fake_submit


# aiida_mlip.data.model.ModelData is a SinglefileData subclass; a custom subclass
# defined only in this test module can't be stored (AiiDA requires Data classes to
# be registered entry points), so SinglefileData itself stands in for it here.
FAKE_MODEL_DATA = orm.SinglefileData


@pytest.fixture
def fake_aiida_mlip(monkeypatch):
    """Inject fake aiida_mlip modules providing the helpers mlip.py imports."""

    def load_structure(value):
        if value == "bad":
            raise ValueError(f"no such structure: {value}")
        return orm.StructureData()

    def load_model(value, architecture, cache_dir=None):
        model = FAKE_MODEL_DATA(content=f"model {architecture}", filename="model.pt")
        model.base.attributes.set("architecture", architecture)
        return model

    help_load = types.ModuleType("aiida_mlip.helpers.help_load")
    help_load.load_structure = load_structure
    help_load.load_model = load_model

    model_module = types.ModuleType("aiida_mlip.data.model")
    model_module.ModelData = FAKE_MODEL_DATA

    modules = {
        "aiida_mlip": types.ModuleType("aiida_mlip"),
        "aiida_mlip.helpers": types.ModuleType("aiida_mlip.helpers"),
        "aiida_mlip.helpers.help_load": help_load,
        "aiida_mlip.data": types.ModuleType("aiida_mlip.data"),
        "aiida_mlip.data.model": model_module,
    }
    for name, module in modules.items():
        monkeypatch.setitem(sys.modules, name, module)

    return load_model


def test_submit_sp_job_builds_validated_inputs(
    code, fake_aiida_mlip, stored_node_returned
):
    """submit_sp_job builds, stores and submits the required inputs."""
    result = mlip.submit_sp_job(
        code=code.pk,
        structure="structure.xyz",
        model="/path/to/model.pt",
        architecture="mace_mp",
        num_machines=2,
        num_mpiprocs_per_machine=4,
    )

    stored_node_returned.assert_called_once()
    submitted = stored_node_returned.call_args.args[1]
    assert submitted["code"].pk == code.pk
    assert isinstance(submitted["struct"], orm.StructureData)
    assert isinstance(submitted["model"], orm.SinglefileData)
    assert "arch" not in submitted  # inferred from the model, not set directly
    resources = submitted["metadata"]["options"]["resources"]
    assert resources == {"num_machines": 2, "num_mpiprocs_per_machine": 4}

    assert result["pk"] == stored_node_returned.return_value.pk
    assert set(result["inputs"]) == {"struct", "model"}
    assert result["code"] == code.full_label


def test_submit_sp_job_includes_optional_inputs(
    code, fake_aiida_mlip, stored_node_returned
):
    """submit_sp_job includes out, properties and calc_kwargs when given."""
    mlip.submit_sp_job(
        code=code.pk,
        structure="structure.xyz",
        architecture="mace_mp",
        device="cpu",
        calc_kwargs={"dispersion": True},
        out="results.xyz",
        properties=["energy", "forces"],
    )

    submitted = stored_node_returned.call_args.args[1]
    assert submitted["arch"].value == "mace_mp"
    assert submitted["device"].value == "cpu"
    assert submitted["calc_kwargs"].get_dict() == {"dispersion": True}
    assert submitted["out"].value == "results.xyz"
    assert submitted["properties"].get_list() == ["energy", "forces"]
    assert "model" not in submitted


def test_submit_job_requires_architecture_for_path_model(
    code, fake_aiida_mlip, fake_submit
):
    """A path/URL model without an architecture is a ToolError."""
    with pytest.raises(ToolError, match="architecture is required"):
        mlip.submit_sp_job(code=code.pk, structure="structure.xyz", model="model.pt")
    fake_submit.assert_not_called()


def test_submit_job_loads_model_by_pk(code, fake_aiida_mlip, stored_node_returned):
    """An existing ModelData node can be reused by PK without an architecture."""
    model_node = FAKE_MODEL_DATA(content="x", filename="model.pt")
    model_node.base.attributes.set("architecture", "mace_mp")
    model_node.store()

    mlip.submit_sp_job(code=code.pk, structure="structure.xyz", model=model_node.pk)

    submitted = stored_node_returned.call_args.args[1]
    assert submitted["model"].pk == model_node.pk
    assert "arch" not in submitted


def test_submit_job_rejects_model_pk_of_wrong_type(code, fake_aiida_mlip, fake_submit):
    """A PK that is not a ModelData node is a ToolError."""
    wrong = orm.Int(1).store()
    with pytest.raises(ToolError, match="expected ModelData"):
        mlip.submit_sp_job(code=code.pk, structure="structure.xyz", model=wrong.pk)
    fake_submit.assert_not_called()


def test_submit_job_wraps_structure_loading_errors(code, fake_aiida_mlip, fake_submit):
    """An error from load_structure is surfaced as a ToolError."""
    with pytest.raises(ToolError, match="structure: no such structure"):
        mlip.submit_sp_job(code=code.pk, structure="bad", architecture="mace_mp")
    fake_submit.assert_not_called()


def test_submit_job_unknown_code_creates_nothing(fake_aiida_mlip, fake_submit):
    """An unknown code is a ToolError and creates no nodes."""
    before = orm.QueryBuilder().append(orm.Node).count()

    with pytest.raises(ToolError, match="No code found"):
        mlip.submit_sp_job(
            code="nope@nowhere", structure="structure.xyz", architecture="mace_mp"
        )

    fake_submit.assert_not_called()
    assert orm.QueryBuilder().append(orm.Node).count() == before


def test_submit_job_rejects_bad_resources(code, fake_aiida_mlip, fake_submit):
    """A resources value below 1 is a ToolError."""
    with pytest.raises(ToolError, match="num_machines must be at least 1"):
        mlip.submit_sp_job(
            code=code.pk,
            structure="structure.xyz",
            architecture="mace_mp",
            num_machines=0,
        )
    fake_submit.assert_not_called()


def test_submit_job_sets_label_and_description(
    code, fake_aiida_mlip, stored_node_returned
):
    """submit_sp_job passes label and description through to the calcjob metadata."""
    mlip.submit_sp_job(
        code=code.pk,
        structure="structure.xyz",
        architecture="mace_mp",
        label="my run",
        description="a test run",
    )

    metadata = stored_node_returned.call_args.args[1]["metadata"]
    assert metadata["label"] == "my run"
    assert metadata["description"] == "a test run"


def test_submit_opt_job_includes_extras(code, fake_aiida_mlip, stored_node_returned):
    """submit_opt_job includes its geometry-optimisation-specific inputs."""
    mlip.submit_opt_job(
        code=code.pk,
        structure="structure.xyz",
        architecture="mace_mp",
        opt_cell_fully=True,
        fmax=0.01,
        steps=100,
        minimize_kwargs={"alpha": 0.1},
        pressure=1.0,
    )

    submitted = stored_node_returned.call_args.args[1]
    assert submitted["opt_cell_fully"].value is True
    assert submitted["fmax"].value == 0.01
    assert submitted["steps"].value == 100
    assert submitted["minimize_kwargs"].get_dict() == {"alpha": 0.1}
    assert submitted["pressure"].value == 1.0
    assert "opt_cell_lengths" not in submitted


def test_submit_md_job_includes_extras(code, fake_aiida_mlip, stored_node_returned):
    """submit_md_job includes its molecular-dynamics-specific inputs."""
    mlip.submit_md_job(
        code=code.pk,
        structure="structure.xyz",
        architecture="mace_mp",
        ensemble="NVT",
        md_kwargs={"temp": 300},
    )

    submitted = stored_node_returned.call_args.args[1]
    assert submitted["ensemble"].value == "NVT"
    assert submitted["md_kwargs"].get_dict() == {"temp": 300}


def test_submit_ph_job_includes_extras(code, fake_aiida_mlip, stored_node_returned):
    """submit_ph_job includes its phonon-specific inputs."""
    mlip.submit_ph_job(
        code=code.pk,
        structure="structure.xyz",
        architecture="mace_mp",
        supercell="2 2 2",
        n_qpoints=50,
        displacement=0.01,
        dos=True,
        symmetrize=True,
    )

    submitted = stored_node_returned.call_args.args[1]
    assert submitted["supercell"].value == "2 2 2"
    assert submitted["n_qpoints"].value == 50
    assert submitted["displacement"].value == 0.01
    assert submitted["dos"].value is True
    assert submitted["symmetrize"].value is True
    assert "pdos" not in submitted
    assert "bands" not in submitted


def test_submit_tools_are_registered_with_input_schema():
    """The MLIP submit and describe tools are registered on the MCP server."""
    server = MCPServer("test")
    mlip.register(server)
    tools = {tool.name: tool for tool in asyncio.run(server.list_tools())}

    expected = {
        "describe_mlip_sp_calcjob",
        "describe_mlip_opt_calcjob",
        "describe_mlip_md_calcjob",
        "describe_mlip_ph_calcjob",
        "submit_mlip_sp_job",
        "submit_mlip_opt_job",
        "submit_mlip_md_job",
        "submit_mlip_ph_job",
    }
    assert set(tools) == expected

    sp_schema = tools["submit_mlip_sp_job"].input_schema
    assert set(sp_schema["required"]) == {"code", "structure"}

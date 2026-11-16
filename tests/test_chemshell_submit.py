"""Tests for building ChemShell input nodes and submitting ChemShell calcjobs."""

import asyncio
import uuid
from unittest import mock

import pytest
from aiida import orm
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from aiida_mcp.plugins import calcjob, chemshell
from aiida_mcp.plugins.inputs import ControlInput, FileInput


@pytest.fixture
def code(aiida_localhost):
    """Return a stored ChemShell code on the test computer."""
    return orm.InstalledCode(
        label=f"chemshell-test-{uuid.uuid4().hex[:8]}",
        computer=aiida_localhost,
        filepath_executable="/bin/true",
        default_calc_job_plugin="chemshell",
    ).store()


@pytest.fixture
def fake_submit():
    """Replace the daemon submit with a stub that returns a process-like node."""
    node = orm.CalcJobNode()
    node.set_process_type("aiida.calculations:chemshell")
    with mock.patch.object(calcjob, "submit", return_value=node) as patched:
        node.store_all = lambda: None
        yield patched


@pytest.fixture
def stored_node_returned(fake_submit):
    """Make the fake submit return an already-stored CalcJobNode."""
    fake_submit.return_value = orm.CalcJobNode().store()
    return fake_submit


def test_submit_job_builds_validated_inputs(code, stored_node_returned):
    """submit_job builds, stores and submits the required inputs."""
    result = chemshell.submit_job(
        code=code.pk,
        structure=FileInput(text="1\n\nH 0.0 0.0 0.0\n"),
        num_machines=2,
        num_mpiprocs_per_machine=8,
    )

    stored_node_returned.assert_called_once()
    submitted = stored_node_returned.call_args.kwargs
    assert submitted["code"].pk == code.pk
    assert submitted["structure"].is_stored
    assert submitted["output_structure_as_file"] is False
    resources = submitted["metadata"]["options"]["resources"]
    assert resources == {"num_machines": 2, "num_mpiprocs_per_machine": 8}

    assert result["pk"] == stored_node_returned.return_value.pk
    assert set(result["inputs"]) == {"structure"}
    assert result["code"] == code.full_label


def test_submit_job_includes_optional_inputs_when_given(code, stored_node_returned):
    """submit_job includes optional inputs only when they are given."""
    chemshell.submit_job(
        code=code.pk,
        structure=FileInput(text="1\n\nH 0.0 0.0 0.0\n"),
        structure_index=2,
        calculation_parameters=ControlInput(parameters={"gradients": True}),
        mm_parameters=ControlInput(parameters={"theory": "DL_POLY"}),
        force_field_file=FileInput(text="FF data"),
        output_structure_as_file=True,
    )

    submitted = stored_node_returned.call_args.kwargs
    assert isinstance(submitted["structure_index"], orm.Int)
    assert submitted["structure_index"].value == 2
    assert isinstance(submitted["calculation_parameters"], orm.Dict)
    assert submitted["calculation_parameters"].get_dict() == {"gradients": True}
    assert isinstance(submitted["force_field_file"], orm.SinglefileData)
    assert submitted["output_structure_as_file"] is True

    unset_names = (
        "structure2",
        "optimisation_parameters",
        "qm_parameters",
        "qmmm_parameters",
    )
    for name in unset_names:
        assert name not in submitted


def test_submit_job_sets_label_and_description(code, stored_node_returned):
    """submit_job passes label and description through to the calcjob metadata."""
    chemshell.submit_job(
        code=code.pk,
        structure=FileInput(text="1\n\nH 0.0 0.0 0.0\n"),
        label="my run",
        description="a test run",
    )

    metadata = stored_node_returned.call_args.kwargs["metadata"]
    assert metadata["label"] == "my run"
    assert metadata["description"] == "a test run"


def test_submit_job_omits_label_and_description_by_default(code, stored_node_returned):
    """submit_job omits label and description from metadata when not given."""
    chemshell.submit_job(code=code.pk, structure=FileInput(text="1\n\nH 0.0 0.0 0.0\n"))

    metadata = stored_node_returned.call_args.kwargs["metadata"]
    assert "label" not in metadata
    assert "description" not in metadata


def test_submit_job_unknown_code_creates_nothing(fake_submit):
    """An unknown code is a ToolError and creates no nodes."""
    before = orm.QueryBuilder().append(orm.Node).count()

    with pytest.raises(ToolError, match="No code found"):
        chemshell.submit_job(
            code="nope@nowhere", structure=FileInput(text="1\n\nH 0.0 0.0 0.0\n")
        )

    fake_submit.assert_not_called()
    assert orm.QueryBuilder().append(orm.Node).count() == before


def test_submit_job_invalid_structure_pk_store_nothing(code, fake_submit):
    """A PK of the wrong node type for structure is a ToolError and creates nothing."""
    wrong = orm.Int(1).store()
    before = orm.QueryBuilder().append(orm.Node).count()
    after_setup = before

    expected = "expected SinglefileData, StructureData, TrajectoryData"
    with pytest.raises(ToolError, match=expected):
        chemshell.submit_job(code=code.pk, structure=FileInput(pk=wrong.pk))

    fake_submit.assert_not_called()
    assert orm.QueryBuilder().append(orm.Node).count() == after_setup


def test_submit_job_rejects_bad_resources(code, fake_submit):
    """A resources value below 1 is a ToolError."""
    with pytest.raises(ToolError, match="num_machines must be at least 1"):
        chemshell.submit_job(
            code=code.pk,
            structure=FileInput(text="1\n\nH 0.0 0.0 0.0\n"),
            num_machines=0,
        )
    fake_submit.assert_not_called()


def test_submit_calcjob_validates_before_storing(aiida_profile, fake_submit):
    """submit_calcjob validates required inputs before storing any of them."""
    unstored = orm.SinglefileData(content="x", filename="structure.xyz")

    with pytest.raises(ToolError, match="Invalid inputs for chemshell"):
        calcjob.submit_calcjob("chemshell", {"structure2": unstored})

    assert not unstored.is_stored
    fake_submit.assert_not_called()


def test_submit_tool_is_registered_with_input_schema():
    """submit_chemshell_job is registered with the expected input schema."""
    server = MCPServer("test")
    chemshell.register(server)
    tools = {tool.name: tool for tool in asyncio.run(server.list_tools())}

    schema = tools["submit_chemshell_job"].input_schema
    assert set(schema["required"]) == {"code", "structure"}
    optional = {
        "structure_index",
        "structure2",
        "calculation_parameters",
        "optimisation_parameters",
        "qm_parameters",
        "mm_parameters",
        "qmmm_parameters",
        "force_field_file",
        "output_structure_as_file",
        "label",
        "description",
    }
    assert optional <= set(schema["properties"])

"""Tests for building DL_POLY input nodes and submitting DL_POLY calcjobs."""

import asyncio
import uuid
from unittest import mock

import pytest
from aiida import orm
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from aiida_mcp.plugins import calcjob, dlpoly
from aiida_mcp.plugins.inputs import ControlInput, FileInput, build_node

SINGLEFILE = (orm.SinglefileData,)


@pytest.fixture
def code(aiida_localhost):
    """Return a stored DL_POLY code on the test computer."""
    return orm.InstalledCode(
        label=f"dlpoly-test-{uuid.uuid4().hex[:8]}",
        computer=aiida_localhost,
        filepath_executable="/bin/true",
        default_calc_job_plugin="dlpoly",
    ).store()


@pytest.fixture
def fake_submit():
    """Replace the daemon submit with a stub that returns a process-like node."""
    node = orm.CalcJobNode()
    node.set_process_type("aiida.calculations:dlpoly")
    with mock.patch.object(calcjob, "submit", return_value=node) as patched:
        node.store_all = lambda: None
        yield patched


@pytest.fixture
def stored_node_returned(fake_submit):
    """Make the fake submit return an already-stored CalcJobNode."""
    fake_submit.return_value = orm.CalcJobNode().store()
    return fake_submit


def _files(tmp_path):
    config = tmp_path / "CONFIG"
    field = tmp_path / "FIELD"
    config.write_text("config text\n")
    field.write_text("field text\n")
    return config, field


def test_build_node_from_path(tmp_path):
    """build_node reads a SinglefileData from a path."""
    config, _ = _files(tmp_path)
    node = build_node(
        FileInput(path=str(config)), "configuration", "CONFIG", SINGLEFILE
    )

    assert isinstance(node, orm.SinglefileData)
    assert node.filename == "CONFIG"
    assert node.get_content() == "config text\n"
    assert not node.is_stored


def test_build_node_from_text():
    """build_node builds a SinglefileData from text."""
    node = build_node(FileInput(text="abc"), "field", "FIELD", SINGLEFILE)

    assert node.filename == "FIELD"
    assert node.get_content() == "abc"


def test_build_node_from_parameters():
    """build_node builds a Dict from parameters."""
    node = build_node(
        ControlInput(parameters={"temperature": [500, "K"]}),
        "control",
        "CONTROL",
        SINGLEFILE,
    )

    assert isinstance(node, orm.Dict)
    assert node.get_dict() == {"temperature": [500, "K"]}


def test_build_node_from_pk(aiida_profile):
    """build_node loads an existing node by PK."""
    stored = orm.SinglefileData(content="x", filename="FIELD").store()
    node = build_node(FileInput(pk=stored.pk), "field", "FIELD", SINGLEFILE)

    assert node.pk == stored.pk


def test_build_node_pk_of_wrong_type(aiida_profile):
    """Loading a PK of the wrong node type is a ToolError."""
    stored = orm.Int(1).store()
    with pytest.raises(ToolError, match="expected SinglefileData"):
        build_node(FileInput(pk=stored.pk), "field", "FIELD", SINGLEFILE)


def test_build_node_missing_pk(aiida_profile):
    """Loading a nonexistent PK is a ToolError."""
    with pytest.raises(ToolError, match="no node with pk 999999"):
        build_node(FileInput(pk=999999), "field", "FIELD", SINGLEFILE)


def test_build_node_missing_file(tmp_path):
    """A path that does not exist is a ToolError."""
    with pytest.raises(ToolError, match="no file at"):
        build_node(FileInput(path=str(tmp_path / "nope")), "field", "FIELD", SINGLEFILE)


@pytest.mark.parametrize("source", [FileInput(), FileInput(path="a", text="b")])
def test_build_node_needs_exactly_one_source(source):
    """Giving zero or more than one source is a ToolError."""
    with pytest.raises(ToolError, match="give exactly one of"):
        build_node(source, "field", "FIELD", SINGLEFILE)


def test_submit_job_builds_validated_inputs(code, tmp_path, stored_node_returned):
    """submit_job builds, stores and submits validated inputs."""
    config, field = _files(tmp_path)
    result = dlpoly.submit_job(
        code=code.pk,
        configuration=FileInput(path=str(config)),
        field=FileInput(path=str(field)),
        control=ControlInput(parameters={"temperature": [500, "K"]}),
        num_machines=2,
        num_mpiprocs_per_machine=4,
    )

    stored_node_returned.assert_called_once()
    submitted = stored_node_returned.call_args.kwargs
    assert submitted["code"].pk == code.pk
    resources = submitted["metadata"]["options"]["resources"]
    assert resources == {"num_machines": 2, "num_mpiprocs_per_machine": 4}
    assert submitted["configuration"].is_stored
    assert submitted["field"].is_stored
    assert submitted["control"].is_stored

    assert result["pk"] == stored_node_returned.return_value.pk
    assert set(result["inputs"]) == {"configuration", "field", "control"}
    assert result["code"] == code.full_label


def test_submit_job_sets_label_and_description(code, tmp_path, stored_node_returned):
    """submit_job passes label and description through to the calcjob metadata."""
    config, field = _files(tmp_path)
    dlpoly.submit_job(
        code=code.pk,
        configuration=FileInput(path=str(config)),
        field=FileInput(path=str(field)),
        control=ControlInput(parameters={}),
        label="my run",
        description="a test run",
    )

    metadata = stored_node_returned.call_args.kwargs["metadata"]
    assert metadata["label"] == "my run"
    assert metadata["description"] == "a test run"


def test_submit_job_omits_label_and_description_by_default(
    code, tmp_path, stored_node_returned
):
    """submit_job omits label and description from metadata when not given."""
    config, field = _files(tmp_path)
    dlpoly.submit_job(
        code=code.pk,
        configuration=FileInput(path=str(config)),
        field=FileInput(path=str(field)),
        control=ControlInput(parameters={}),
    )

    metadata = stored_node_returned.call_args.kwargs["metadata"]
    assert "label" not in metadata
    assert "description" not in metadata


def test_submit_job_accepts_code_label(code, tmp_path, stored_node_returned):
    """submit_job accepts a code's full label as well as its PK."""
    config, field = _files(tmp_path)
    dlpoly.submit_job(
        code=code.full_label,
        configuration=FileInput(path=str(config)),
        field=FileInput(path=str(field)),
        control=ControlInput(text="title t\n"),
    )

    assert stored_node_returned.call_args.kwargs["code"].pk == code.pk


def test_submit_job_unknown_code_creates_nothing(tmp_path, fake_submit):
    """An unknown code is a ToolError and creates no nodes."""
    config, field = _files(tmp_path)
    before = orm.QueryBuilder().append(orm.Node).count()

    with pytest.raises(ToolError, match="No code found"):
        dlpoly.submit_job(
            code="nope@nowhere",
            configuration=FileInput(path=str(config)),
            field=FileInput(path=str(field)),
            control=ControlInput(parameters={}),
        )

    fake_submit.assert_not_called()
    assert orm.QueryBuilder().append(orm.Node).count() == before


def test_submit_job_invalid_inputs_store_nothing(code, tmp_path, fake_submit):
    """Invalid inputs are a ToolError and store no new nodes."""
    config, field = _files(tmp_path)
    before = orm.QueryBuilder().append(orm.Node).count()
    wrong = orm.Int(1).store()
    after_setup = before + 1

    with pytest.raises(ToolError, match="expected SinglefileData, Dict"):
        dlpoly.submit_job(
            code=code.pk,
            configuration=FileInput(path=str(config)),
            field=FileInput(path=str(field)),
            control=ControlInput(pk=wrong.pk),
        )

    fake_submit.assert_not_called()
    assert orm.QueryBuilder().append(orm.Node).count() == after_setup


def test_submit_job_rejects_bad_resources(code, tmp_path, fake_submit):
    """A resources value below 1 is a ToolError."""
    config, field = _files(tmp_path)
    with pytest.raises(ToolError, match="num_machines must be at least 1"):
        dlpoly.submit_job(
            code=code.pk,
            configuration=FileInput(path=str(config)),
            field=FileInput(path=str(field)),
            control=ControlInput(parameters={}),
            num_machines=0,
        )
    fake_submit.assert_not_called()


def test_submit_calcjob_validates_before_storing(aiida_profile, fake_submit):
    """submit_calcjob validates inputs before storing any of them."""
    unstored = orm.SinglefileData(content="x", filename="FIELD")

    with pytest.raises(ToolError, match="Invalid inputs for dlpoly"):
        calcjob.submit_calcjob("dlpoly", {"field": unstored})

    assert not unstored.is_stored
    fake_submit.assert_not_called()


def test_submit_calcjob_unknown_plugin(fake_submit):
    """Submitting to an uninstalled plugin is a ToolError."""
    with pytest.raises(ToolError, match="not installed"):
        calcjob.submit_calcjob("no-such-plugin", {})


def test_submit_tool_is_registered_with_input_schema():
    """submit_dlpoly_job is registered with the expected input schema."""
    server = MCPServer("test")
    dlpoly.register(server)
    tools = {tool.name: tool for tool in asyncio.run(server.list_tools())}

    schema = tools["submit_dlpoly_job"].input_schema
    assert set(schema["required"]) == {"code", "configuration", "field", "control"}
    assert {"label", "description"} <= set(schema["properties"])
    assert {"path", "text", "pk"} <= set(schema["$defs"]["FileInput"]["properties"])
    assert "parameters" in schema["$defs"]["ControlInput"]["properties"]

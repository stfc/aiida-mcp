"""Tests for the generic input-building helpers in aiida_mcp.plugins.inputs."""

import pytest
from aiida import orm
from mcp.server.mcpserver.exceptions import ToolError

from aiida_mcp.plugins.inputs import ControlInput, FileInput, build_node

SINGLEFILE = (orm.SinglefileData,)


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

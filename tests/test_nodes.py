import pytest
from aiida import orm
from aiida.engine import calcfunction, run_get_node
from mcp.server.mcpserver.exceptions import ToolError

from aiida_mcp import nodes


@calcfunction
def add(x, y):
    return x + y


@pytest.fixture
def localhost(aiida_localhost):
    return aiida_localhost


@pytest.fixture
def code(localhost):
    return orm.InstalledCode(
        label="addcode",
        computer=localhost,
        filepath_executable="/bin/true",
        default_calc_job_plugin="core.arithmetic.add",
    ).store()


def test_list_computers_includes_localhost(localhost):
    result = nodes.list_computers()
    assert localhost.label in [c["label"] for c in result["computers"]]
    assert result["total"] == len(result["computers"])


def test_list_codes_returns_stored_code(code):
    result = nodes.list_codes(limit=50)
    labels = [c["label"] for c in result["codes"]]
    assert "addcode" in labels
    entry = next(c for c in result["codes"] if c["label"] == "addcode")
    assert entry["default_calc_job_plugin"] == "core.arithmetic.add"
    assert entry["computer"] == code.computer.label


def test_list_codes_filters_by_computer(code, localhost):
    matching = nodes.list_codes(computer=localhost.label, limit=50)
    assert "addcode" in [c["label"] for c in matching["codes"]]

    missing = nodes.list_codes(computer="no-such-computer", limit=50)
    assert missing["total_matching"] == 0
    assert missing["codes"] == []


def test_list_codes_rejects_zero_limit():
    with pytest.raises(ToolError, match="limit must be at least 1"):
        nodes.list_codes(limit=0)


def test_query_nodes_by_type_prefix():
    orm.Int(1).store()
    orm.Int(2).store()
    orm.Str("not an int").store()

    result = nodes.query_nodes(node_type="data.core.int", limit=50)
    assert result["total_matching"] >= 2
    assert all("data.core.int" in n["node_type"] for n in result["nodes"])


def test_query_nodes_accepts_trailing_percent():
    orm.Int(7).store()
    with_percent = nodes.query_nodes(node_type="data.core.int%", limit=50)
    without = nodes.query_nodes(node_type="data.core.int", limit=50)
    assert with_percent["total_matching"] == without["total_matching"]


def test_query_nodes_by_group():
    node = orm.Int(42).store()
    group = orm.Group(label="stage4-tests").store()
    group.add_nodes([node])

    result = nodes.query_nodes(group="stage4-tests", limit=50)
    assert [n["pk"] for n in result["nodes"]] == [node.pk]


def test_query_nodes_unknown_group_is_tool_error():
    with pytest.raises(ToolError, match="No group labelled 'nope'"):
        nodes.query_nodes(group="nope")


def test_query_nodes_by_extra_key():
    tagged = orm.Int(3)
    tagged.base.extras.set("stage4_marker", True)
    tagged.store()
    untagged = orm.Int(4).store()

    result = nodes.query_nodes(extra_key="stage4_marker", limit=50)
    pks = [n["pk"] for n in result["nodes"]]
    assert tagged.pk in pks
    assert untagged.pk not in pks


def test_query_nodes_finds_process_nodes():
    _, node = run_get_node(add, x=orm.Int(1), y=orm.Int(1))
    result = nodes.query_nodes(node_type="process", limit=50)
    assert node.pk in [n["pk"] for n in result["nodes"]]


def test_get_node_content_returns_text(tmp_path):
    path = tmp_path / "hello.txt"
    path.write_text("hello world")
    node = orm.SinglefileData(file=str(path)).store()

    result = nodes.get_node_content(node.pk)
    assert result["filename"] == "hello.txt"
    assert result["encoding"] == "utf-8"
    assert result["truncated"] is False
    assert result["content"] == "hello world"


def test_get_node_content_base64_encodes_binary(tmp_path):
    path = tmp_path / "binary.dat"
    path.write_bytes(b"\xff\xfe\x00\x01")
    node = orm.SinglefileData(file=str(path)).store()

    result = nodes.get_node_content(node.pk)
    assert result["encoding"] == "base64"
    import base64

    assert base64.b64decode(result["content"]) == b"\xff\xfe\x00\x01"


def test_get_node_content_truncates_large_files(tmp_path, monkeypatch):
    monkeypatch.setattr(nodes, "MAX_FILE_BYTES", 5)
    path = tmp_path / "big.txt"
    path.write_text("0123456789")
    node = orm.SinglefileData(file=str(path)).store()

    result = nodes.get_node_content(node.pk)
    assert result["truncated"] is True
    assert result["content"] == "01234"


def test_get_node_content_returns_int_value():
    node = orm.Int(42).store()
    result = nodes.get_node_content(node.pk)
    assert result["content"] == 42


def test_get_node_content_returns_float_value():
    node = orm.Float(3.14).store()
    result = nodes.get_node_content(node.pk)
    assert result["content"] == 3.14


def test_get_node_content_rejects_missing_node():
    with pytest.raises(ToolError, match="No node with pk"):
        nodes.get_node_content(999999)


def test_get_node_content_rejects_unsupported_node_type():
    node = orm.Str("not supported").store()
    with pytest.raises(ToolError, match="only supported for:"):
        nodes.get_node_content(node.pk)

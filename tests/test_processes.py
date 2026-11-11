import pytest
from aiida import orm
from aiida.engine import run_get_node, calcfunction
from mcp.server.mcpserver.exceptions import ToolError

from aiida_mcp import processes


@calcfunction
def add(x, y):
    return x + y


@calcfunction
def boom(x):
    raise RuntimeError("deliberate failure")


@pytest.fixture
def finished_node(aiida_profile):
    _, node = run_get_node(add, x=orm.Int(2), y=orm.Int(3))
    return node


@pytest.fixture
def excepted_node(aiida_profile):
    before = _max_pk()
    with pytest.raises(RuntimeError):
        run_get_node(boom, x=orm.Int(1))
    return _newest_process_after(before, "boom")


def _max_pk() -> int:
    qb = orm.QueryBuilder().append(orm.Node, project=["id"]).order_by({orm.Node: {"id": "desc"}}).limit(1)
    rows = qb.all(flat=True)
    return rows[0] if rows else 0


def _newest_process_after(pk: int, label: str) -> orm.ProcessNode:
    qb = (
        orm.QueryBuilder()
        .append(orm.ProcessNode, filters={"id": {">": pk}, "attributes.process_label": label}, project=["*"])
        .order_by({orm.ProcessNode: {"id": "desc"}})
        .limit(1)
    )
    return qb.one()[0]


def test_list_processes_includes_finished_run(finished_node):
    result = processes.list_processes(limit=50)
    pks = [p["pk"] for p in result["processes"]]
    assert finished_node.pk in pks


def test_list_processes_filters_by_state(finished_node, excepted_node):
    finished = processes.list_processes(state="finished", limit=50)
    assert all(p["state"] == "finished" for p in finished["processes"])
    assert finished_node.pk in [p["pk"] for p in finished["processes"]]

    excepted = processes.list_processes(state="excepted", limit=50)
    assert excepted_node.pk in [p["pk"] for p in excepted["processes"]]
    assert all(p["state"] == "excepted" for p in excepted["processes"])


def test_list_processes_filters_by_label(finished_node, excepted_node):
    result = processes.list_processes(label="boom", limit=50)
    assert result["processes"]
    assert all(p["label"] == "boom" for p in result["processes"])


def test_list_processes_limit_is_respected(finished_node, excepted_node):
    result = processes.list_processes(limit=1)
    assert result["returned"] == 1
    assert result["total_matching"] >= 2


def test_list_processes_rejects_unknown_state():
    with pytest.raises(ToolError, match="Unknown state"):
        processes.list_processes(state="bogus")


def test_list_processes_rejects_zero_limit():
    with pytest.raises(ToolError, match="limit must be at least 1"):
        processes.list_processes(limit=0)


def test_get_process_shows_inputs_and_outputs(finished_node):
    result = processes.get_process(finished_node.pk)
    assert result["pk"] == finished_node.pk
    assert result["state"] == "finished"
    assert result["exit_status"] == 0
    assert sorted(i["label"] for i in result["inputs"]) == ["x", "y"]
    assert [o["label"] for o in result["outputs"]] == ["result"]


def test_get_process_missing_pk_is_tool_error():
    with pytest.raises(ToolError, match="No node with pk 999999"):
        processes.get_process(999999)


def test_get_process_non_process_node_is_tool_error(finished_node):
    data_pk = finished_node.inputs.x.pk
    with pytest.raises(ToolError, match="not a process"):
        processes.get_process(data_pk)


def test_get_process_report_contains_traceback(excepted_node):
    result = processes.get_process_report(excepted_node.pk)
    assert result["total_logs"] >= 1
    assert any("deliberate failure" in log["message"] for log in result["logs"])


def test_get_process_report_limit_keeps_most_recent(excepted_node):
    full = processes.get_process_report(excepted_node.pk, limit=1000)
    limited = processes.get_process_report(excepted_node.pk, limit=1)
    assert limited["returned"] == 1
    assert limited["logs"][0] == full["logs"][-1]

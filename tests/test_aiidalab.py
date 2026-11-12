"""Tests for AiiDAlab Jupyter server detection."""

from unittest import mock

from aiida_mcp import aiidalab

ANY_SERVER = {
    "url": "http://localhost:8888/",
    "token": "abc123",
    "root_dir": "/home/user/notebooks",
    "pid": 111,
    "version": "2.16.0",
}

AIIDALAB_SERVER = {**ANY_SERVER, "root_dir": "/home/aiida/.aiidalab"}


def _patch_servers(servers):
    return mock.patch(
        "jupyter_server.serverapp.list_running_servers", return_value=servers
    )


def test_get_status_reports_not_running_when_no_servers():
    """No running Jupyter server means running is False."""
    with _patch_servers([]):
        assert aiidalab.get_status() == {"running": False}


def test_get_status_falls_back_to_sole_server():
    """A single running server is reported even if its root_dir isn't named aiidalab."""
    with _patch_servers([ANY_SERVER]):
        result = aiidalab.get_status()

    assert result["running"] is True
    assert result["url"] == "http://localhost:8888/?token=abc123"
    assert result["root_dir"] == "/home/user/notebooks"


def test_get_status_matches_aiidalab_root_dir():
    """A server whose root_dir mentions aiidalab is reported as running."""
    with _patch_servers([AIIDALAB_SERVER]):
        result = aiidalab.get_status()

    assert result["running"] is True
    assert result["pid"] == 111
    assert result["root_dir"] == "/home/aiida/.aiidalab"


def test_get_status_prefers_aiidalab_match_among_several():
    """Among several servers, only the aiidalab-matching one is reported."""
    other = {**ANY_SERVER, "root_dir": "/home/other/work"}
    with _patch_servers([other, AIIDALAB_SERVER]):
        result = aiidalab.get_status()

    assert result["running"] is True
    assert "ambiguous" not in result
    assert result["root_dir"] == "/home/aiida/.aiidalab"


def test_get_status_reports_ambiguous_for_multiple_unmatched_servers():
    """Multiple servers with no aiidalab match are reported as ambiguous."""
    other = {**ANY_SERVER, "root_dir": "/home/other/work"}
    with _patch_servers([ANY_SERVER, other]):
        result = aiidalab.get_status()

    assert result["running"] is True
    assert result["ambiguous"] is True
    assert len(result["servers"]) == 2


def test_get_status_reports_unavailable_without_jupyter_server():
    """If jupyter_server is not installed, get_status reports an error."""
    with mock.patch.dict("sys.modules", {"jupyter_server.serverapp": None}):
        result = aiidalab.get_status()

    assert result["running"] is False
    assert "jupyter_server" in result["error"]

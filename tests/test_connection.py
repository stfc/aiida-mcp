from unittest import mock

from aiida_mcp import connection


def test_status_reports_loaded_profile(aiida_profile):
    status = connection.get_status()
    assert status["profile_loaded"] is True
    assert status["profile"] == aiida_profile.name


def test_status_skips_broker_check_when_daemon_stopped(aiida_profile):
    with mock.patch.object(connection, "get_daemon_client") as client:
        client.return_value.is_daemon_running = False
        status = connection.get_status()

    assert status["daemon_running"] is False
    assert status["broker_connected"] is None
    assert "broker_note" in status


def test_status_reports_broker_error_without_raising(aiida_profile):
    with (
        mock.patch.object(connection, "get_daemon_client") as client,
        mock.patch.object(connection, "get_manager") as manager,
    ):
        client.return_value.is_daemon_running = True
        manager.return_value.get_communicator.side_effect = RuntimeError("no broker")
        status = connection.get_status()

    assert status["broker_connected"] is False
    assert "no broker" in status["broker_error"]


def test_status_reports_missing_profile_without_raising(monkeypatch):
    def fail():
        raise RuntimeError("no config")

    monkeypatch.setattr(connection, "get_profile", lambda: None)
    monkeypatch.setattr(connection, "load_profile", fail)
    status = connection.get_status()

    assert status["profile_loaded"] is False
    assert "no config" in status["error"]

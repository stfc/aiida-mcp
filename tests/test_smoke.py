from aiida_mcp import connection, server


def test_ping():
    assert server.ping() == "pong"


def test_status_uses_isolated_profile(aiida_profile):
    status = connection.get_status()
    assert status["profile_loaded"] is True
    assert status["profile"] == aiida_profile.name
    assert status["profile"] != "presto"

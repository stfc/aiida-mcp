"""Basic smoke tests that the server and test isolation work."""

from aiida_mcp import connection, server


def test_ping():
    """The ping tool responds."""
    assert server.ping() == "pong"


def test_status_uses_isolated_profile(aiida_profile):
    """Tests run against the isolated test profile, not a real one."""
    status = connection.get_status()
    assert status["profile_loaded"] is True
    assert status["profile"] == aiida_profile.name
    assert status["profile"] != "presto"

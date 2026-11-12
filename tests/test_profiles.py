"""Tests for AiiDA profile listing, creation and switching."""

import uuid

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from aiida_mcp import profiles


def _name() -> str:
    return f"mcp-test-{uuid.uuid4().hex[:8]}"


def test_list_profiles_includes_current(aiida_profile):
    """The currently loaded profile is listed and flagged as current."""
    result = profiles.list_profiles()

    assert result["current"] == aiida_profile.name
    entry = next(p for p in result["profiles"] if p["name"] == aiida_profile.name)
    assert entry["is_current"] is True
    assert entry["storage_backend"] == aiida_profile.storage_backend


def test_create_profile_creates_and_lists(tmp_path, aiida_profile):
    """A created profile shows up in list_profiles without changing the current one."""
    name = _name()
    result = profiles.create_profile(
        name=name,
        email="test@example.com",
        storage_config={"filepath": str(tmp_path / "storage")},
    )

    assert result["name"] == name
    assert result["storage_backend"] == profiles.DEFAULT_STORAGE_BACKEND
    assert result["is_default"] is False

    listed = profiles.list_profiles()
    assert name in [p["name"] for p in listed["profiles"]]
    assert listed["current"] == aiida_profile.name


def test_create_profile_set_as_default(tmp_path, aiida_profile):
    """set_as_default=True makes the new profile the on-disk default."""
    from aiida.manage.configuration import get_config

    config = get_config()
    name = _name()

    try:
        result = profiles.create_profile(
            name=name,
            email="test@example.com",
            storage_config={"filepath": str(tmp_path / "storage")},
            set_as_default=True,
        )
        assert result["is_default"] is True
        assert config.default_profile_name == name
    finally:
        config.set_default_profile(aiida_profile.name, overwrite=True)
        config.store()


def test_create_profile_rejects_duplicate_name(aiida_profile):
    """Creating a profile with an existing name is a ToolError."""
    with pytest.raises(ToolError, match="already exists"):
        profiles.create_profile(name=aiida_profile.name, email="test@example.com")


def test_create_profile_requires_email_for_non_readonly_backend(tmp_path):
    """A non-read-only storage backend requires an email for the default user."""
    with pytest.raises(ToolError, match="email is required"):
        profiles.create_profile(
            name=_name(), storage_config={"filepath": str(tmp_path / "storage")}
        )


def test_create_profile_rejects_unknown_storage_backend():
    """An unrecognised storage_backend entry point is a ToolError."""
    with pytest.raises(ToolError, match="Unknown storage backend"):
        profiles.create_profile(
            name=_name(), email="test@example.com", storage_backend="no-such-backend"
        )


def test_create_profile_rejects_unknown_broker():
    """An unrecognised broker choice is a ToolError."""
    with pytest.raises(ToolError, match="broker must be one of"):
        profiles.create_profile(
            name=_name(), email="test@example.com", broker="no-such-broker"
        )


def test_switch_profile_rejects_unknown_name():
    """Switching to a name that is not a configured profile is a ToolError."""
    with pytest.raises(ToolError, match="No profile named"):
        profiles.switch_profile("no-such-profile")


def test_switch_profile_roundtrip(tmp_path, aiida_profile):
    """Switching to a profile and back restores the originally loaded profile."""
    name = _name()
    profiles.create_profile(
        name=name,
        email="test@example.com",
        storage_config={"filepath": str(tmp_path / "storage")},
    )

    try:
        switched = profiles.switch_profile(name)
        assert switched["current"] == name
    finally:
        restored = profiles.switch_profile(aiida_profile.name)
        assert restored["current"] == aiida_profile.name

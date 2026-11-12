"""AiiDA profile listing, creation and switching."""

from typing import Any

import pydantic
from aiida import load_profile
from aiida.common import exceptions
from aiida.manage.configuration import create_profile as _create_profile
from aiida.manage.configuration import get_config, get_profile
from aiida.plugins import BrokerFactory, StorageFactory
from aiida.plugins.entry_point import get_entry_point_names
from mcp.server.mcpserver.exceptions import ToolError

from aiida_mcp import connection

DEFAULT_STORAGE_BACKEND = "core.sqlite_dos"
BROKER_CHOICES = ["none", "core.rabbitmq", "core.zeromq"]


def list_profiles() -> dict[str, Any]:
    """List all configured AiiDA profiles."""
    config = get_config()
    current = get_profile()

    profiles = []
    for name in config.profile_names:
        profile = config.get_profile(name)
        profiles.append(
            {
                "name": profile.name,
                "storage_backend": profile.storage_backend,
                "broker_backend": profile.process_control_backend,
                "is_test_profile": profile.is_test_profile,
                "is_default": name == config.default_profile_name,
                "is_current": current is not None and name == current.name,
            }
        )

    return {
        "current": current.name if current is not None else None,
        "default": config.default_profile_name,
        "profiles": profiles,
    }


def create_profile(
    name: str,
    email: str | None = None,
    storage_backend: str = DEFAULT_STORAGE_BACKEND,
    storage_config: dict[str, Any] | None = None,
    broker: str = "none",
    first_name: str | None = None,
    last_name: str | None = None,
    institution: str | None = None,
    set_as_default: bool = False,
) -> dict[str, Any]:
    """Create a new AiiDA profile and initialise its storage.

    This does not switch the server's active profile; call switch_profile for that.
    """
    if broker not in BROKER_CHOICES:
        raise ToolError(f"broker must be one of: {', '.join(BROKER_CHOICES)}")

    storage_backends = get_entry_point_names("aiida.storage")
    if storage_backend not in storage_backends:
        choices = ", ".join(storage_backends)
        message = f"Unknown storage backend {storage_backend!r}. Choose from: {choices}"
        raise ToolError(message)

    if not StorageFactory(storage_backend).read_only and email is None:
        raise ToolError(f"email is required for storage backend {storage_backend!r}")

    with connection.lock():
        config = get_config()
        if name in config.profile_names:
            raise ToolError(f"A profile named {name!r} already exists")

        broker_backend, broker_config = _resolve_broker(broker)

        try:
            profile = _create_profile(
                config,
                name=name,
                email=email,
                first_name=first_name,
                last_name=last_name,
                institution=institution,
                storage_backend=storage_backend,
                storage_config=storage_config or {},
                broker_backend=broker_backend,
                broker_config=broker_config,
            )
        except (
            ValueError,
            TypeError,
            pydantic.ValidationError,
            exceptions.EntryPointError,
            exceptions.StorageMigrationError,
        ) as exc:
            raise ToolError(f"Could not create profile {name!r}: {exc}") from exc

        if set_as_default:
            config.set_default_profile(name, overwrite=True)
            config.store()

    return {
        "name": profile.name,
        "storage_backend": profile.storage_backend,
        "broker_backend": profile.process_control_backend,
        "is_default": config.default_profile_name == name,
    }


def switch_profile(name: str) -> dict[str, Any]:
    """Switch the server's active AiiDA profile and initialise its storage."""
    config = get_config()
    if name not in config.profile_names:
        known = ", ".join(config.profile_names)
        raise ToolError(f"No profile named {name!r}. Known profiles: {known}")

    with connection.lock():
        load_profile(name, allow_switch=True)

    connection.ensure_profile()
    return list_profiles()


def _resolve_broker(broker: str) -> tuple[str | None, dict[str, Any] | None]:
    if broker == "none":
        return None, None

    if broker == "core.zeromq":
        return broker, BrokerFactory(broker).get_default_config()

    import aiida.brokers.rabbitmq.defaults as rabbitmq_defaults

    try:
        return broker, rabbitmq_defaults.detect_rabbitmq_config()
    except ConnectionError as exc:
        raise ToolError(f"RabbitMQ server not reachable: {exc}") from exc

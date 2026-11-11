import threading
from typing import Any

from aiida import load_profile
from aiida.engine.daemon.client import get_daemon_client
from aiida.manage import get_manager
from aiida.manage.configuration import get_profile

_lock = threading.Lock()


def ensure_profile() -> None:
    """Load the default AiiDA profile and initialise its storage once, safe across threads."""
    with _lock:
        if get_profile() is None:
            load_profile()
        get_manager().get_profile_storage()


def get_status() -> dict[str, Any]:
    """Report the AiiDA profile, daemon and broker status without raising."""
    try:
        ensure_profile()
    except Exception as exc:
        return {"profile_loaded": False, "error": f"{type(exc).__name__}: {exc}"}

    profile = get_profile()
    daemon_running = get_daemon_client(profile.name).is_daemon_running
    status: dict[str, Any] = {
        "profile_loaded": True,
        "profile": profile.name,
        "daemon_running": daemon_running,
        "broker_configured": profile.process_control_backend is not None,
        "broker_connected": None,
    }

    if not daemon_running:
        status["broker_note"] = "Not checked: the daemon is not running, and connecting would block."
        return status

    try:
        get_manager().get_communicator()
        status["broker_connected"] = True
    except Exception as exc:
        status["broker_connected"] = False
        status["broker_error"] = f"{type(exc).__name__}: {exc}"

    return status

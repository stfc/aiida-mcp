"""Shared handling for tool `limit` arguments."""

from mcp.server.mcpserver.exceptions import ToolError


def clamp_limit(value: int | None, default: int, maximum: int) -> int:
    """Clamp a requested limit to [1, maximum], falling back to default when None.

    Parameters
    ----------
    value : int or None
        The requested limit, or None to use the default.
    default : int
        The value to use when `value` is None.
    maximum : int
        The upper bound to clamp `value` to.

    Returns
    -------
    int
        The clamped limit.

    Raises
    ------
    ToolError
        If `value` is less than 1.
    """
    if value is None:
        return default
    if value < 1:
        raise ToolError(f"limit must be at least 1, got {value}")
    return min(int(value), maximum)

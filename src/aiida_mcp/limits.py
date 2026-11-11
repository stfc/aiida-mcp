from mcp.server.mcpserver.exceptions import ToolError


def clamp_limit(value: int | None, default: int, maximum: int) -> int:
    if value is None:
        return default
    if value < 1:
        raise ToolError(f"limit must be at least 1, got {value}")
    return min(int(value), maximum)

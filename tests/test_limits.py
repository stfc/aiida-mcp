import pytest
from mcp.server.mcpserver.exceptions import ToolError

from aiida_mcp.limits import clamp_limit


def test_none_uses_default():
    assert clamp_limit(None, default=20, maximum=200) == 20


def test_value_within_range_is_returned():
    assert clamp_limit(5, default=20, maximum=200) == 5


def test_value_above_maximum_is_capped():
    assert clamp_limit(500, default=20, maximum=200) == 200


@pytest.mark.parametrize("value", [0, -1])
def test_value_below_one_is_rejected(value):
    with pytest.raises(ToolError, match="limit must be at least 1"):
        clamp_limit(value, default=20, maximum=200)

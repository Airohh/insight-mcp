"""Bootstrap smoke test — replaced by real tool tests in phase 1."""

import insight_mcp


def test_package_importable():
    assert insight_mcp.__version__

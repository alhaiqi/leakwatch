import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))
FIX = ROOT / "tests" / "fixtures"


def pytest_configure(config):
    config.addinivalue_line("markers", "live: hits real gateway/GitHub/OpenRouter (opt-in: -m live)")


def pytest_collection_modifyitems(config, items):
    if "live" in (config.getoption("-m") or ""):
        return
    skip = pytest.mark.skip(reason="live test; run with -m live")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip)


@pytest.fixture
def positive():
    import fakes
    text, values = fakes.fill((FIX / "positive.diff").read_text())
    expected = json.loads((FIX / "positive.expected.json").read_text())
    return text, values, expected


@pytest.fixture
def placeholders():
    return (FIX / "placeholders.diff").read_text()

import os, sys, pytest
import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "perf: performance benchmark (see test/performance_test)"
    )

@pytest.fixture
def dummy_path(tmp_path):
    return str(tmp_path / "dummy.file")
import pytest
from pathlib import Path

INTERFACE_DATA_DIR = Path(__file__).parent / "tests/data"


@pytest.fixture(autouse=True)
def prepare_namespace(doctest_namespace):
    doctest_namespace["data_path"] = INTERFACE_DATA_DIR

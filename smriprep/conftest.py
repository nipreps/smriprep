import os
from pathlib import Path
from tempfile import TemporaryDirectory
import pytest

os.environ['NO_ET'] = '1'


@pytest.fixture(autouse=True, scope="session")
def default_cwd():
    cwd = os.getcwd()
    with TemporaryDirectory(prefix="smriprepTest") as tmpdir:
        try:
            os.chdir(tmpdir)
            yield Path(tmpdir)
        finally:
            os.chdir(cwd)


@pytest.fixture(autouse=True, scope="session")
def populate_default_cwd(default_cwd):
    Path.write_bytes(default_cwd / 'lh.white', b'')

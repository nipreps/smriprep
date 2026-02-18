import os
from pathlib import Path
from shutil import copytree

import numpy as np
import pytest

from smriprep.data import load

os.environ['NO_ET'] = '1'

try:
    from contextlib import chdir as _chdir
except ImportError:  # PY310
    from contextlib import contextmanager

    @contextmanager  # type: ignore
    def _chdir(path):
        cwd = os.getcwd()
        os.chdir(path)
        try:
            yield
        finally:
            os.chdir(cwd)


@pytest.fixture(autouse=True)
def _populate_namespace(doctest_namespace, tmp_path):
    doctest_namespace['os'] = os
    doctest_namespace['np'] = np
    doctest_namespace['load'] = load
    doctest_namespace['testdir'] = tmp_path


@pytest.fixture(autouse=True)
def _docdir(request, tmp_path):
    # Trigger ONLY for doctests within smriprep.interfaces.*.
    doctest_plugin = request.config.pluginmanager.getplugin('doctest')
    if (
        doctest_plugin
        and isinstance(request.node, doctest_plugin.DoctestItem)
        and request.node.dtest.globs.get('__name__', '').startswith('smriprep.interfaces')
    ):
        copytree(Path(__file__).parent / 'interfaces' / 'data', tmp_path, dirs_exist_ok=True)

        # Chdir only for the duration of the test.
        with _chdir(tmp_path):
            yield
    else:
        # For normal tests, we have to yield, since this is a yield-fixture.
        yield

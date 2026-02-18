from pathlib import Path
from shutil import copytree

import pytest


@pytest.fixture(autouse=True)
def _docdir(request, tmp_path, monkeypatch):
    doctest_plugin = request.config.pluginmanager.getplugin('doctest')
    if not (
        doctest_plugin
        and isinstance(request.node, doctest_plugin.DoctestItem)
        and request.node.dtest.globs.get('__name__', '').startswith('smriprep.interfaces')
    ):
        yield
        return

    copytree(
        Path(request.config.rootpath) / 'test' / 'interfaces' / 'data',
        tmp_path,
        dirs_exist_ok=True,
    )
    monkeypatch.chdir(tmp_path)
    yield

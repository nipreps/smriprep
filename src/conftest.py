# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
#
# Copyright The NiPreps Developers <nipreps@gmail.com>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# We support and encourage derived works from this project, please read
# about our expectations at
#
#     https://www.nipreps.org/community/licensing/
#
import os
from pathlib import Path
from shutil import copytree

import numpy as np
import pytest

from smriprep.data import load

os.environ['NO_ET'] = '1'


@pytest.fixture(autouse=True)
def _populate_namespace(doctest_namespace, tmp_path):
    doctest_namespace['os'] = os
    doctest_namespace['np'] = np
    doctest_namespace['load'] = load
    doctest_namespace['testdir'] = tmp_path


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

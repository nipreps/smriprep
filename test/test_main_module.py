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
"""Tests for ``python -m smriprep`` entrypoint."""

import runpy
import sys


def test_main_module_rewrites_argv_and_calls_main(monkeypatch):
    captured = {}

    def _fake_main():
        captured['argv0'] = sys.argv[0]

    monkeypatch.setattr('smriprep.cli.run.main', _fake_main)
    monkeypatch.setattr(sys, 'argv', ['/mock/__main__.py'])

    runpy.run_module('smriprep.__main__', run_name='__main__')
    assert captured['argv0'] == f'{sys.executable} -m smriprep'

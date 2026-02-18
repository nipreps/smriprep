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
"""Unit tests for CLI helpers in ``smriprep.cli.run``."""

import sys
import types
from argparse import Namespace

import pytest

from smriprep.cli import run


class _FakeSpaces:
    def __init__(self):
        self._cached = False
        self.checkpoint_calls = 0

    def is_cached(self):
        return self._cached

    def checkpoint(self):
        self._cached = True
        self.checkpoint_calls += 1

    def __str__(self):
        return 'MNI152NLin2009cAsym'


def _make_cli_opts(tmp_path, **overrides):
    defaults = {
        'bids_dir': tmp_path / 'bids',
        'output_dir': tmp_path / 'out',
        'analysis_level': 'participant',
        'participant_label': None,
        'session_label': None,
        'derivatives': [],
        'bids_filter_file': None,
        'subject_anatomical_reference': 'first-lex',
        'nprocs': 2,
        'omp_nthreads': 0,
        'mem_gb': 0,
        'low_mem': False,
        'use_plugin': None,
        'boilerplate': False,
        'verbose_count': 0,
        'output_spaces': _FakeSpaces(),
        'longitudinal': False,
        'skull_strip_template': ['OASIS30ANTs'],
        'skull_strip_fixed_seed': False,
        'skull_strip_mode': 'auto',
        'fs_license_file': None,
        'fs_subjects_dir': None,
        'fs_no_resume': False,
        'cifti_output': False,
        'hires': True,
        'msm_sulc': True,
        'run_reconall': False,
        'work_dir': tmp_path / 'work',
        'fast_track': False,
        'resource_monitor': False,
        'reports_only': False,
        'run_uuid': None,
        'write_graph': False,
        'stop_on_first_crash': False,
        'notrack': False,
        'sloppy': False,
    }
    defaults.update(overrides)
    return Namespace(**defaults)


def test_main_handles_longitudinal_deprecation(monkeypatch):
    opts = Namespace(longitudinal=True, subject_anatomical_reference='first-lex')

    class _Parser:
        def parse_args(self):
            return opts

    monkeypatch.setattr(run, 'get_parser', lambda: _Parser())
    monkeypatch.setattr(run, 'build_opts', lambda parsed: parsed)
    result = run.main()
    assert result.subject_anatomical_reference == 'unbiased'
    assert result.longitudinal is True


def test_main_sets_longitudinal_if_unbiased(monkeypatch):
    opts = Namespace(longitudinal=False, subject_anatomical_reference='unbiased')

    class _Parser:
        def parse_args(self):
            return opts

    monkeypatch.setattr(run, 'get_parser', lambda: _Parser())
    monkeypatch.setattr(run, 'build_opts', lambda parsed: parsed)
    result = run.main()
    assert result.longitudinal is True


def test_check_deps(monkeypatch):
    class _MissingInterface:
        _cmd = 'missing_cmd --flag'

    class _PresentInterface:
        _cmd = 'present_cmd --flag'

    class _NoCmdInterface:
        pass

    class _Workflow:
        def _get_all_nodes(self):
            return [
                Namespace(interface=_PresentInterface()),
                Namespace(interface=_MissingInterface()),
                Namespace(interface=_NoCmdInterface()),
            ]

    monkeypatch.setattr(
        'nipype.utils.filemanip.which',
        lambda cmd: None if cmd == 'missing_cmd' else f'/usr/bin/{cmd}',
    )
    assert run.check_deps(_Workflow()) == [('_MissingInterface', 'missing_cmd --flag')]


def test_pprint_subses():
    subses = [('01', 'A'), ('02', ['A', 'B']), ('03', None), ('04', ['A'])]
    assert run._pprint_subses(subses) == 'sub-01 ses-A, sub-02 (2 sessions), sub-03, sub-04 ses-A'


def test_build_workflow_reports_only(monkeypatch, tmp_path):
    opts = _make_cli_opts(tmp_path, reports_only=True, run_uuid='manual-run-id')
    opts.bids_dir.mkdir(parents=True, exist_ok=True)

    class _Layout:
        def __init__(self, root, **_kwargs):
            self.root = root

        def get_sessions(self, **_kwargs):
            return ['pre']

    calls = {}

    fake_base = types.ModuleType('smriprep.workflows.base')
    fake_base.init_smriprep_wf = lambda **_kwargs: None
    monkeypatch.setitem(sys.modules, 'smriprep.workflows.base', fake_base)
    monkeypatch.setattr('bids.layout.BIDSLayout', _Layout)
    monkeypatch.setattr('niworkflows.utils.bids.collect_participants', lambda *_a, **_k: ['01'])
    monkeypatch.setattr(
        'nireports.assembler.tools.generate_reports',
        lambda subject_session_list, smriprep_dir, run_uuid, bootstrap_file: (
            calls.update(
                {
                    'subject_session_list': subject_session_list,
                    'run_uuid': run_uuid,
                    'smriprep_dir': smriprep_dir,
                }
            )
            or 0
        ),
    )

    retval = {}
    result = run.build_workflow(opts, retval)
    assert result['return_code'] == 0
    assert result['workflow'] is None
    assert calls['subject_session_list'] == [('01', ['pre'])]
    assert calls['run_uuid'] == 'manual-run-id'
    assert calls['smriprep_dir'] == opts.output_dir.resolve() / 'smriprep'


def test_build_workflow_full(monkeypatch, tmp_path):
    opts = _make_cli_opts(tmp_path, reports_only=False, run_reconall=False)
    opts.bids_dir.mkdir(parents=True, exist_ok=True)

    class _Layout:
        def __init__(self, root, **_kwargs):
            self.root = root

        def get_sessions(self, **_kwargs):
            return ['pre']

    class _FakeWorkflow:
        def visit_desc(self):
            return 'boilerplate'

    fake_workflow = _FakeWorkflow()

    fake_base = types.ModuleType('smriprep.workflows.base')
    fake_base.init_smriprep_wf = lambda **_kwargs: fake_workflow
    monkeypatch.setitem(sys.modules, 'smriprep.workflows.base', fake_base)
    monkeypatch.setattr('bids.layout.BIDSLayout', _Layout)
    monkeypatch.setattr('niworkflows.utils.bids.collect_participants', lambda *_a, **_k: ['01'])
    monkeypatch.setattr(
        'subprocess.check_call', lambda *args, **kwargs: (_ for _ in ()).throw(FileNotFoundError)
    )

    retval = {}
    result = run.build_workflow(opts, retval)
    assert result['workflow'] is fake_workflow
    assert result['plugin_settings']['plugin_args']['n_procs'] == 2
    assert result['return_code'] == 0
    assert opts.output_spaces.checkpoint_calls == 1


class _Manager:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def dict(self):
        return {}


class _Process:
    def __init__(self, target, args):
        self._target = target
        self._args = args
        self.exitcode = 0

    def start(self):
        self._target(*self._args)

    def join(self):
        return None


def _populate_retval(retval, workflow):
    retval['workflow'] = workflow
    retval['plugin_settings'] = {'plugin': 'MultiProc', 'plugin_args': {}}
    retval['bids_dir'] = '/mock/bids'
    retval['output_dir'] = '/mock/out'
    retval['subject_session_list'] = [('01', None)]
    retval['run_uuid'] = '20260101-000000_uuid'
    retval['return_code'] = 0


def test_build_opts_requires_valid_fs_license(monkeypatch, tmp_path):
    opts = _make_cli_opts(tmp_path)
    monkeypatch.setattr('multiprocessing.set_start_method', lambda *_a, **_k: None)
    monkeypatch.setattr('niworkflows.utils.misc.check_valid_fs_license', lambda: False)
    with pytest.raises(RuntimeError, match='valid license file'):
        run.build_opts(opts)


def test_build_opts_exits_on_missing_deps(monkeypatch, tmp_path):
    opts = _make_cli_opts(tmp_path, run_reconall=False)

    class _Workflow:
        pass

    monkeypatch.setattr('multiprocessing.set_start_method', lambda *_a, **_k: None)
    monkeypatch.setattr('multiprocessing.Manager', _Manager)
    monkeypatch.setattr('multiprocessing.Process', _Process)
    monkeypatch.setattr('niworkflows.utils.misc.check_valid_fs_license', lambda: True)
    monkeypatch.setattr(
        run, 'build_workflow', lambda _opts, retval: _populate_retval(retval, _Workflow())
    )
    monkeypatch.setattr(run, 'check_deps', lambda *_a, **_k: [('Iface', 'missing_cmd')])

    with pytest.raises(SystemExit, match='2'):
        run.build_opts(opts)


def test_build_opts_runs_and_finalizes(monkeypatch, tmp_path):
    opts = _make_cli_opts(tmp_path, run_reconall=False)
    calls = {'ran': False, 'desc': False, 'ignore': False, 'reports': False}

    class _Workflow:
        def run(self, **_kwargs):
            calls['ran'] = True

    monkeypatch.setattr('multiprocessing.set_start_method', lambda *_a, **_k: None)
    monkeypatch.setattr('multiprocessing.Manager', _Manager)
    monkeypatch.setattr('multiprocessing.Process', _Process)
    monkeypatch.setattr('niworkflows.utils.misc.check_valid_fs_license', lambda: True)
    monkeypatch.setattr(
        run, 'build_workflow', lambda _opts, retval: _populate_retval(retval, _Workflow())
    )
    monkeypatch.setattr(run, 'check_deps', lambda *_a, **_k: [])
    monkeypatch.setattr(
        'nireports.assembler.tools.generate_reports',
        lambda *_a, **_k: calls.__setitem__('reports', True) or 0,
    )
    monkeypatch.setattr(
        'smriprep.utils.bids.write_derivative_description',
        lambda *_a, **_k: calls.__setitem__('desc', True),
    )
    monkeypatch.setattr(
        'smriprep.utils.bids.write_bidsignore', lambda *_a, **_k: calls.__setitem__('ignore', True)
    )

    with pytest.raises(SystemExit, match='0'):
        run.build_opts(opts)

    assert calls['ran'] is True
    assert calls['reports'] is True
    assert calls['desc'] is True
    assert calls['ignore'] is True

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
import json

import nibabel as nb
import numpy as np
import pytest
from niworkflows.utils.testing import generate_bids_skeleton

from smriprep.cli.run import build_workflow, get_parser

NO_SESSION_LAYOUT = {
    '01': [
        {
            'anat': [
                {'run': 1, 'suffix': 'T1w'},
                {'run': 2, 'acq': 'test', 'suffix': 'T1w'},
                {'suffix': 'T2w'},
            ],
        },
    ],
}

SESSION_LAYOUT = {
    '01': [
        {
            'session': 'pre',
            'anat': [
                {'run': 1, 'suffix': 'T1w'},
                {'run': 2, 'acq': 'test', 'suffix': 'T1w'},
                {'suffix': 'T2w'},
            ],
        },
        {
            'session': 'post',
            'anat': [
                {'run': 1, 'suffix': 'T1w'},
                {'run': 2, 'acq': 'test', 'suffix': 'T1w'},
                {'suffix': 'T2w'},
            ],
        },
    ],
}


@pytest.fixture(scope='module')
def bids_no_session(tmp_path_factory):
    base = tmp_path_factory.mktemp('bids_dirs')
    bids_dir = base / 'no_session'
    generate_bids_skeleton(bids_dir, NO_SESSION_LAYOUT)

    img = nb.Nifti1Image(np.zeros((10, 10, 10, 10)), np.eye(4))

    for path in bids_dir.glob('sub-01/**/*.nii.gz'):
        img.to_filename(path)
    return bids_dir


@pytest.fixture(scope='module')
def bids_session(tmp_path_factory):
    base = tmp_path_factory.mktemp('bids_dirs')
    bids_dir = base / 'with_session'
    generate_bids_skeleton(bids_dir, SESSION_LAYOUT)

    img = nb.Nifti1Image(np.zeros((10, 10, 10, 10)), np.eye(4))

    for path in bids_dir.glob('sub-01/**/*.nii.gz'):
        img.to_filename(path)
    return bids_dir


T1_FILTER = {
    't1w': {
        'acquisition': None,
        'session': ['post'],
    }
}


@pytest.mark.parametrize(
    ('session', 'additional_args', 'filters', 'fail'),
    [
        (False, [], None, False),
        (True, [], None, False),
        (True, ['--subject-anatomical-reference', 'sessionwise'], None, False),
        (True, ['--subject-anatomical-reference', 'sessionwise'], T1_FILTER, True),
        (True, ['--session-label', 'pre'], None, False),
        (True, ['--session-label', 'pre'], T1_FILTER, True),
        (True, ['--session-label', 'post'], None, False),
    ],
)
def test_build_workflow(
    monkeypatch,
    tmp_path,
    bids_no_session,
    bids_session,
    session,
    additional_args,
    filters,
    fail,
):
    parser = get_parser()
    bids_dir = bids_no_session if not session else bids_session
    base_args = [
        str(bids_dir),
        str(bids_dir / 'derivatives' / 'smriprep'),
        'participant',
        '--participant-label',
        '01',
    ]
    if filters:
        filter_file = bids_session / '.filter.json'
        filter_file.write_text(json.dumps(filters))
        additional_args += ['--bids-filter-file', str(filter_file)]

    base_args += additional_args
    pargs = parser.parse_args(base_args)

    fs_dir = tmp_path / 'freesurfer'
    fs_dir.mkdir()
    monkeypatch.setenv('FREESURFER_HOME', str(fs_dir))
    monkeypatch.setenv('SUBJECTS_DIR', str(fs_dir))

    if fail:
        with pytest.raises(ValueError, match='Conflicting entities'):
            build_workflow(pargs, {})
        return

    ret = build_workflow(pargs, {})
    assert ret['workflow']


@pytest.mark.parametrize('precomputed', [False, True])
def test_build_workflow_precomputed_surfaces(
    monkeypatch,
    tmp_path,
    bids_no_session,
    deriv_dset,
    precomputed,
):
    """FreeSurfer is not run if all derivatives that depend on it were precomputed."""
    args = [
        str(bids_no_session),
        str(tmp_path / 'output'),
        'participant',
        '--participant-label',
        '01',
    ]
    if precomputed:
        args += ['--derivatives', str(deriv_dset())]
    pargs = get_parser().parse_args(args)

    fs_dir = tmp_path / 'freesurfer'
    fs_dir.mkdir()
    monkeypatch.setenv('FREESURFER_HOME', str(fs_dir))
    monkeypatch.setenv('SUBJECTS_DIR', str(fs_dir))

    workflow = build_workflow(pargs, {})['workflow']
    subject_wf = workflow.get_node('sub-01_wf')
    nodes = subject_wf.list_node_names()
    assert ('anat_preproc_wf.anat_fit_wf.surface_recon_wf.autorecon1' in nodes) is not precomputed

    # Nor is a subjects directory prepared, which would copy fsaverage into the outputs
    has_fsdir = any(name.startswith('fsdir_run_') for name in workflow.list_node_names())
    assert has_fsdir is not precomputed

    # The summary only inspects the FreeSurfer subject if one is reconstructed
    summary = subject_wf.get_node('summary')
    fields = {
        dest
        for *_, data in subject_wf._graph.in_edges(summary, data=True)
        for _, dest in data['connect']
    }
    assert ('subjects_dir' in fields) is not precomputed

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

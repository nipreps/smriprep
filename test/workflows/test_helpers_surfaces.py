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
"""Tests for surface workflow helpers."""

from pathlib import Path

import numpy as np
import pytest

from smriprep.workflows.surfaces import (
    _check_cw256,
    _check_subjects_dir,
    _extract_fs_fields,
    _get_surfaces,
    _repeat,
    _select_seg,
    _sorted_by_basename,
)


def test_check_cw256(make_nifti, tmp_path):
    large = make_nifti(tmp_path / 'large.nii.gz', data=np.zeros((257, 1, 1)))
    small = make_nifti(tmp_path / 'small.nii.gz', data=np.zeros((64, 64, 64)))
    assert '-cw256' in _check_cw256(large, ['-noskullstrip'])
    assert '-cw256' not in _check_cw256(small, ['-noskullstrip'])


def test_sorted_by_basename():
    inlist = ['/x/c.nii.gz', '/y/a.nii.gz', '/z/b.nii.gz']
    assert _sorted_by_basename(inlist) == ['/y/a.nii.gz', '/z/b.nii.gz', '/x/c.nii.gz']


def test_extract_fs_fields(tmp_path):
    files = []
    for hemi in ('lh', 'rh'):
        path = tmp_path / 'freesurfer' / 'sub-01' / 'surf' / f'{hemi}.white'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('x')
        files.append(str(path))

    subjects_dir, subject_id = _extract_fs_fields(files)
    assert subjects_dir.endswith('freesurfer')
    assert subject_id == 'sub-01'

    bad = tmp_path / 'freesurfer' / 'sub-02' / 'surf' / 'lh.white'
    bad.parent.mkdir(parents=True, exist_ok=True)
    bad.write_text('x')
    with pytest.raises(ValueError, match='Expected surface files from one subject'):
        _extract_fs_fields(files + [str(bad)])


def test_get_surfaces_with_graymid_fallback(tmp_path):
    surf_dir = tmp_path / 'freesurfer' / 'sub-01' / 'surf'
    surf_dir.mkdir(parents=True)
    for name in (
        'lh.white',
        'rh.white',
        'lh.graymid',
        'rh.graymid',
        'lh.sphere.reg',
        'rh.sphere.reg',
    ):
        (surf_dir / name).write_text('x')

    white, midthickness, sphere_reg = _get_surfaces(
        str(tmp_path / 'freesurfer'),
        'sub-01',
        ['white', 'midthickness', 'sphere_reg'],
    )
    assert len(white) == 2
    assert len(midthickness) == 2
    assert all('graymid' in surf for surf in midthickness)
    assert all('sphere.reg' in surf for surf in sphere_reg)


def test_select_seg_and_repeat():
    assert _select_seg('aparc+aseg.mgz', 'aparc_aseg') == 'aparc+aseg.mgz'
    assert _select_seg(['a2009s+aseg.mgz', 'aparc+aseg.mgz'], 'aparc_aseg') == 'aparc+aseg.mgz'
    assert _repeat(['L', 'R'], 2) == ['L', 'R', 'L', 'R']
    with pytest.raises(FileNotFoundError):
        _select_seg(['wmparc.mgz'], 'aparc_aseg')


def test_check_subjects_dir(tmp_path):
    with pytest.raises(FileNotFoundError):
        _check_subjects_dir(tmp_path / 'missing', 'sub-01')

    subjects_dir = tmp_path / 'freesurfer'
    subjects_dir.mkdir()
    with pytest.raises(FileNotFoundError):
        _check_subjects_dir(subjects_dir, 'sub-01')

    (subjects_dir / 'sub-01').mkdir()
    assert _check_subjects_dir(subjects_dir, 'sub-01') == (str(subjects_dir), 'sub-01')

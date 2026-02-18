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
"""Tests for anatomical workflow helper functions."""

import nibabel as nb
import numpy as np

from smriprep.workflows.anatomical import (
    _aseg_to_three,
    _is_skull_stripped,
    _pop,
    _probseg_fast2bids,
    _split_segments,
)


def test_anatomical_helpers_simple():
    assert _pop(['a']) == 'a'
    assert _pop(('a', 'b')) == 'a'
    assert _pop('a') == 'a'
    assert _probseg_fast2bids(['CSF', 'WM', 'GM']) == ('WM', 'GM', 'CSF')


def test_aseg_to_three_mapping():
    lut = _aseg_to_three()
    assert len(lut) == 256
    assert lut[3] == 1  # GM
    assert lut[2] == 2  # WM
    assert lut[4] == 3  # CSF


def test_split_segments(make_nifti, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    in_file = make_nifti(
        tmp_path / 'seg.nii.gz',
        data=np.array([[[0, 1], [2, 3]]], dtype='uint8'),
    )
    out_files = _split_segments(in_file)
    assert len(out_files) == 3
    gm, wm, csf = [np.asanyarray(nb.load(path).dataobj).astype(bool) for path in out_files]
    assert np.array_equal(gm, np.array([[[False, True], [False, False]]], dtype=bool))
    assert np.array_equal(wm, np.array([[[False, False], [True, False]]], dtype=bool))
    assert np.array_equal(csf, np.array([[[False, False], [False, True]]], dtype=bool))


def test_is_skull_stripped(make_nifti, tmp_path):
    stripped = np.zeros((5, 5, 5), dtype='float32')
    stripped[2, 2, 2] = 10
    not_stripped = stripped.copy()
    not_stripped[0, 2, 2] = 20

    stripped_file = make_nifti(tmp_path / 'stripped.nii.gz', data=stripped)
    not_stripped_file = make_nifti(tmp_path / 'not_stripped.nii.gz', data=not_stripped)
    assert bool(_is_skull_stripped(stripped_file))
    assert not bool(_is_skull_stripped(not_stripped_file))

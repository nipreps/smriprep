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
import pytest
from niworkflows.utils.testing import generate_bids_skeleton

from smriprep.utils.bids import collect_derivatives

from . import DERIV_SKELETON


@pytest.fixture
def deriv_dset(tmp_path):
    deriv_dir = tmp_path / 'derivatives'
    generate_bids_skeleton(deriv_dir, str(DERIV_SKELETON))
    return deriv_dir


def test_collect_derivatives(deriv_dset):
    output_spaces = ['MNI152NLin2009cAsym', 'MNIPediatricAsym:cohort-3']
    collected = collect_derivatives(deriv_dset, '01', output_spaces)
    for suffix in ('preproc', 'mask', 'dseg'):
        assert collected[f't1w_{suffix}']
    assert len(collected['t1w_tpms']) == 3
    xfms = collected['transforms']
    for space in output_spaces:
        assert xfms[space]['reverse']
        assert xfms[space]['forward']
    for surface in (
        'white',
        'pial',
        'midthickness',
        'sphere',
        'thickness',
        'sulc',
        'sphere_reg',
        'sphere_reg_fsLR',
        'sphere_reg_msm',
    ):
        assert len(collected[surface]) == 2


def test_collect_derivatives_transforms(deriv_dset):
    """Ensure transforms are collected for the right spaces."""
    output_spaces = ['MNI152NLin2009cAsym', 'MNIPediatricAsym:cohort-3']
    collected = collect_derivatives(deriv_dset, '01', output_spaces)
    xfms = collected['transforms']
    for space in output_spaces:
        template = space.split(':')[0]
        assert template in xfms[space]['reverse']
        assert template in xfms[space]['forward']

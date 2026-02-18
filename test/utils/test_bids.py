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


class _FakeItem:
    def __init__(self, path, label=None):
        self.path = path
        self.entities = {}
        if label is not None:
            self.entities['label'] = label


def test_collect_derivatives_respects_session_id(monkeypatch):
    class _FakeLayout:
        def __init__(self, *_args, **_kwargs):
            self.calls = []

        def get(self, return_type=None, **qry):
            self.calls.append(qry)
            if qry.get('suffix') == 'T1w' and qry.get('desc') == 'preproc':
                return [_FakeItem('/tmp/sub-01_ses-pre_desc-preproc_T1w.nii.gz')]
            if qry.get('suffix') == 'xfm':
                path = '/tmp/sub-01_ses-pre_from-T1w_to-MNI152NLin2009cAsym_xfm.h5'
                return [path] if return_type == 'filename' else [_FakeItem(path)]
            return []

    fake_layout = _FakeLayout()
    monkeypatch.setattr('smriprep.utils.bids.BIDSLayout', lambda *_a, **_k: fake_layout)
    monkeypatch.setattr('smriprep.utils.bids.nwf_load', lambda *_a, **_k: 'nipreps.json')

    spec = {
        'baseline': {'preproc': {'suffix': 'T1w', 'desc': 'preproc'}},
        'transforms': {
            'forward': {'suffix': 'xfm', 'from': 'T1w', 'to': None},
        },
        'surfaces': {},
        'masks': {},
    }

    collected = collect_derivatives(
        '/tmp/derivs',
        '01',
        ['MNI152NLin2009cAsym'],
        spec=spec,
        patterns={},
        session_id='pre',
    )

    assert collected['t1w_preproc'].endswith('desc-preproc_T1w.nii.gz')
    assert collected['transforms']['MNI152NLin2009cAsym']['forward'].endswith('_xfm.h5')
    assert all(call.get('session') == 'pre' for call in fake_layout.calls)


def test_collect_derivatives_partial_transforms(monkeypatch):
    class _FakeLayout:
        def __init__(self, *_args, **_kwargs):
            pass

        def get(self, return_type=None, **qry):
            from_space = qry.get('from')
            to_space = qry.get('to')
            if qry.get('suffix') != 'xfm':
                return []
            if from_space == 'T1w' and to_space == 'MNI152NLin2009cAsym':
                return (
                    ['/tmp/fwd-mni.h5']
                    if return_type == 'filename'
                    else [_FakeItem('/tmp/fwd-mni.h5')]
                )
            if from_space == 'MNIPediatricAsym+3' and to_space == 'T1w':
                return (
                    ['/tmp/rev-pediatric.h5']
                    if return_type == 'filename'
                    else [_FakeItem('/tmp/rev-pediatric.h5')]
                )
            return []

    monkeypatch.setattr('smriprep.utils.bids.BIDSLayout', _FakeLayout)
    monkeypatch.setattr('smriprep.utils.bids.nwf_load', lambda *_a, **_k: 'nipreps.json')

    spec = {
        'baseline': {},
        'transforms': {
            'forward': {'suffix': 'xfm', 'from': 'T1w', 'to': None},
            'reverse': {'suffix': 'xfm', 'from': None, 'to': 'T1w'},
        },
        'surfaces': {},
        'masks': {},
    }

    collected = collect_derivatives(
        '/tmp/derivs',
        '01',
        ['MNI152NLin2009cAsym', 'MNIPediatricAsym:cohort-3'],
        spec=spec,
        patterns={},
    )
    assert collected['transforms']['MNI152NLin2009cAsym'] == {'forward': '/tmp/fwd-mni.h5'}
    assert collected['transforms']['MNIPediatricAsym:cohort-3'] == {
        'reverse': '/tmp/rev-pediatric.h5'
    }


def test_collect_derivatives_enforces_surface_and_mask_cardinality(monkeypatch):
    class _FakeLayout:
        def __init__(self, *_args, **_kwargs):
            pass

        def get(self, return_type=None, **qry):
            if qry.get('suffix') == 'white':
                files = ['/tmp/lh.white.surf.gii']  # Missing right hemisphere
                return files if return_type == 'filename' else [_FakeItem(files[0])]
            if qry.get('suffix') == 'mask':
                files = ['/tmp/ribbon1.nii.gz', '/tmp/ribbon2.nii.gz']  # Should be exactly one
                return files if return_type == 'filename' else [_FakeItem(fl) for fl in files]
            return []

    monkeypatch.setattr('smriprep.utils.bids.BIDSLayout', _FakeLayout)
    monkeypatch.setattr('smriprep.utils.bids.nwf_load', lambda *_a, **_k: 'nipreps.json')

    spec = {
        'baseline': {},
        'transforms': {},
        'surfaces': {'white': {'suffix': 'white'}},
        'masks': {'anat_ribbon': {'suffix': 'mask'}},
    }
    collected = collect_derivatives('/tmp/derivs', '01', [], spec=spec, patterns={})
    assert 'white' not in collected
    assert 'anat_ribbon' not in collected


def test_collect_derivatives_respects_label_query_order(monkeypatch):
    class _FakeLayout:
        def __init__(self, *_args, **_kwargs):
            pass

        def get(self, return_type=None, **qry):
            if qry.get('suffix') == 'probseg':
                items = [
                    _FakeItem('/tmp/label-CSF_probseg.nii.gz', label='CSF'),
                    _FakeItem('/tmp/label-GM_probseg.nii.gz', label='GM'),
                    _FakeItem('/tmp/label-WM_probseg.nii.gz', label='WM'),
                ]
                return items
            return []

    monkeypatch.setattr('smriprep.utils.bids.BIDSLayout', _FakeLayout)
    monkeypatch.setattr('smriprep.utils.bids.nwf_load', lambda *_a, **_k: 'nipreps.json')

    spec = {
        'baseline': {
            'tpms': {'suffix': 'probseg', 'label': ['GM', 'WM', 'CSF']},
        },
        'transforms': {},
        'surfaces': {},
        'masks': {},
    }
    collected = collect_derivatives('/tmp/derivs', '01', [], spec=spec, patterns={})
    assert collected['t1w_tpms'] == [
        '/tmp/label-GM_probseg.nii.gz',
        '/tmp/label-WM_probseg.nii.gz',
        '/tmp/label-CSF_probseg.nii.gz',
    ]

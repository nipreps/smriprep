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
import logging
from pathlib import Path

import pytest
from niworkflows.utils.testing import generate_bids_skeleton

from smriprep.utils.bids import collect_anat_derivatives, collect_derivatives

from . import deriv_skeleton

IMAGES = ['t1w_preproc', 't2w_preproc', 't1w_mask', 't1w_dseg', 't1w_tpms', 'anat_ribbon']
SURFACES = [
    'white',
    'pial',
    'midthickness',
    'sphere',
    'sphere_reg',
    'sphere_reg_fsLR',
    'sphere_reg_msm',
    'thickness',
    'sulc',
    'curv',
    'cortex_mask',
]


def _entity(path, name):
    """Extract an entity value from a BIDS filename."""
    for part in Path(path).name.split('_'):
        if part.startswith(f'{name}-'):
            return part.split('-', 1)[1]
    return None


def _paths(collected):
    """Flatten every path out of a (nested) collection result."""
    if isinstance(collected, str):
        return [collected]
    values = collected.values() if isinstance(collected, dict) else collected
    return [path for value in values for path in _paths(value)]


def test_deriv_skeleton_include():
    full = deriv_skeleton()
    assert full.keys() == {'dataset_description', '01'}
    assert len(sub01 := full['01']) == 1
    assert sub01[0].keys() == {'anat'}
    assert len(anat := sub01[0]['anat']) == 36  # This can change if we modify the skeleton
    # Spot check a few of the expected entries
    assert {'suffix': 'T1w', 'desc': 'preproc'} in anat
    assert {'suffix': 'thickness', 'hemi': 'R', 'extension': '.shape.gii'} in anat
    assert {
        'suffix': 'xfm',
        'from': 'T1w',
        'to': 'MNI152NLin2009cAsym',
        'mode': 'image',
        'extension': '.h5',
    } in anat

    assert deriv_skeleton([])['01'][0]['anat'] == []
    assert len(deriv_skeleton(['t1w_tpms'])['01'][0]['anat']) == 3
    # 2 TPMs + 1 mask
    partial = deriv_skeleton({'t1w_tpms': 2, 't1w_mask': True, 't1w_dseg': False})
    assert len(partial['01'][0]['anat']) == 3

    with_session = deriv_skeleton(['t1w_mask'], subject='02', session='A')
    assert with_session['02'] == [{'session': 'A', 'anat': [{'suffix': 'mask', 'desc': 'brain'}]}]

    with pytest.raises(KeyError, match='masque'):
        deriv_skeleton(['masque'])


def test_collect_anat_derivatives(deriv_dset):
    collected = collect_anat_derivatives([deriv_dset()], '01', ['MNI152NLin2009cAsym'])

    assert sorted(set(collected) - {'transforms'}) == sorted(IMAGES + SURFACES)
    assert [_entity(path, 'label') for path in collected['t1w_tpms']] == ['GM', 'WM', 'CSF']
    for surface in SURFACES:
        assert [_entity(path, 'hemi') for path in collected[surface]] == ['L', 'R']

    xfms = collected['transforms']
    assert sorted(xfms) == ['MNI152NLin2009cAsym', 'fsnative']
    for space, xfm in xfms.items():
        assert sorted(xfm) == ['forward', 'reverse']
        assert _entity(xfm['forward'], 'to') == space
        assert _entity(xfm['reverse'], 'from') == space


@pytest.mark.parametrize('derivatives', ['none', 'empty'])
def test_collect_anat_derivatives_nothing(deriv_dset, derivatives):
    """With no derivatives (or an empty dataset), nothing is collected."""
    dirs = [] if derivatives == 'none' else [deriv_dset([])]
    assert _paths(collect_anat_derivatives(dirs, '01', ['MNI152NLin2009cAsym'])) == []


@pytest.mark.parametrize(
    ('include', 'key'),
    [
        pytest.param(
            {'t1w_tpms': 2},
            't1w_tpms',
            marks=pytest.mark.xfail(
                strict=True,
                reason='collect_derivatives does not check the number of tissue probability maps',
            ),
        ),
        ({'white': 1}, 'white'),
        ({'sphere_reg_msm': 1}, 'sphere_reg_msm'),
        ({'cortex_mask': 1}, 'cortex_mask'),
    ],
)
def test_collect_anat_derivatives_incomplete(deriv_dset, include, key):
    """A multi-file derivative with missing files is not collected."""
    collected = collect_anat_derivatives([deriv_dset(include)], '01', [])
    assert key not in collected


def test_collect_anat_derivatives_one_direction(deriv_dset):
    deriv_dir = deriv_dset({'xfm_MNI152NLin2009cAsym': 1})
    collected = collect_anat_derivatives([deriv_dir], '01', ['MNI152NLin2009cAsym'])
    assert sorted(collected['transforms']['MNI152NLin2009cAsym']) == ['forward']


def test_collect_anat_derivatives_session(deriv_dset):
    deriv_dir = deriv_dset(['t1w_mask'], session='A')

    collected = collect_anat_derivatives([deriv_dir], '01', [], session_id='A')
    assert _entity(collected['t1w_mask'], 'ses') == 'A'

    collected = collect_anat_derivatives([deriv_dir], '01', [], session_id='B')
    assert _paths(collected) == []


def test_collect_anat_derivatives_subject(deriv_dset):
    deriv_dir = deriv_dset(['t1w_mask'])
    assert _paths(collect_anat_derivatives([deriv_dir], '02', [])) == []


def test_collect_anat_derivatives_cohort(deriv_dset):
    """Transforms are found for cohort spaces, keyed by their TemplateFlow name."""
    collected = collect_anat_derivatives(
        [deriv_dset()], '01', ['MNI152NLin2009cAsym', 'MNIPediatricAsym:cohort-3']
    )
    xfms = collected['transforms']['MNIPediatricAsym:cohort-3']
    assert _entity(xfms['forward'], 'to') == 'MNIPediatricAsym+3'
    assert _entity(xfms['reverse'], 'from') == 'MNIPediatricAsym+3'


def test_collect_derivatives(deriv_dset):
    output_spaces = ['MNI152NLin2009cAsym', 'MNIPediatricAsym:cohort-3']
    collected = collect_derivatives(deriv_dset(), '01', output_spaces)
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


@pytest.mark.parametrize(
    ('sphere_reg_entities', 'expected', 'warns'),
    [
        pytest.param([{'desc': 'reg'}], [None, None], True, id='without-fsaverage'),
        pytest.param(
            [{'space': 'fsaverage', 'desc': 'reg'}],
            ['fsaverage', 'fsaverage'],
            False,
            id='with-fsaverage',
        ),
        # Four matching files is ambiguous, so nothing is reused
        pytest.param(
            [{'desc': 'reg'}, {'space': 'fsaverage', 'desc': 'reg'}],
            None,
            False,
            id='both',
        ),
    ],
)
def test_collect_anat_derivatives_reuses_sphere_reg(
    tmp_path, caplog, sphere_reg_entities, expected, warns
):
    """The fsaverage registration sphere is reusable under both naming conventions."""
    skeleton = {
        '01': [
            {
                'anat': [
                    {
                        'suffix': 'sphere',
                        'hemi': hemi,
                        'extension': '.surf.gii',
                        **entities,
                    }
                    for entities in sphere_reg_entities
                    for hemi in ('L', 'R')
                ]
            }
        ]
    }
    deriv_dir = tmp_path / 'derivatives'
    generate_bids_skeleton(deriv_dir, skeleton)

    with caplog.at_level(logging.WARNING, logger='nipype.workflow'):
        collected = collect_anat_derivatives([deriv_dir], '01', [])

    spheres = collected.get('sphere_reg')
    assert ([_entity(path, 'space') for path in spheres] if spheres else None) == expected
    assert any('legacy sphere_reg' in record.message for record in caplog.records) is warns


def test_collect_derivatives_transforms(deriv_dset):
    """Ensure transforms are collected for the right spaces."""
    output_spaces = ['MNI152NLin2009cAsym', 'MNIPediatricAsym:cohort-3']
    collected = collect_derivatives(deriv_dset(), '01', output_spaces)
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
                return [_FakeItem('/mock/sub-01_ses-pre_desc-preproc_T1w.nii.gz')]
            if qry.get('suffix') == 'xfm':
                path = '/mock/sub-01_ses-pre_from-T1w_to-MNI152NLin2009cAsym_xfm.h5'
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
        '/mock/derivs',
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
                    ['/mock/fwd-mni.h5']
                    if return_type == 'filename'
                    else [_FakeItem('/mock/fwd-mni.h5')]
                )
            if from_space == 'MNIPediatricAsym+3' and to_space == 'T1w':
                return (
                    ['/mock/rev-pediatric.h5']
                    if return_type == 'filename'
                    else [_FakeItem('/mock/rev-pediatric.h5')]
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
        '/mock/derivs',
        '01',
        ['MNI152NLin2009cAsym', 'MNIPediatricAsym:cohort-3'],
        spec=spec,
        patterns={},
    )
    assert collected['transforms']['MNI152NLin2009cAsym'] == {'forward': '/mock/fwd-mni.h5'}
    assert collected['transforms']['MNIPediatricAsym:cohort-3'] == {
        'reverse': '/mock/rev-pediatric.h5'
    }


def test_collect_derivatives_enforces_surface_and_mask_cardinality(monkeypatch):
    class _FakeLayout:
        def __init__(self, *_args, **_kwargs):
            pass

        def get(self, return_type=None, **qry):
            if qry.get('suffix') == 'white':
                files = ['/mock/lh.white.surf.gii']  # Missing right hemisphere
                return files if return_type == 'filename' else [_FakeItem(files[0])]
            if qry.get('suffix') == 'mask':
                files = ['/mock/ribbon1.nii.gz', '/mock/ribbon2.nii.gz']  # Should be exactly one
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
    collected = collect_derivatives('/mock/derivs', '01', [], spec=spec, patterns={})
    assert 'white' not in collected
    assert 'anat_ribbon' not in collected


def test_collect_derivatives_respects_label_query_order(monkeypatch):
    class _FakeLayout:
        def __init__(self, *_args, **_kwargs):
            pass

        def get(self, return_type=None, **qry):
            if qry.get('suffix') == 'probseg':
                items = [
                    _FakeItem('/mock/label-CSF_probseg.nii.gz', label='CSF'),
                    _FakeItem('/mock/label-GM_probseg.nii.gz', label='GM'),
                    _FakeItem('/mock/label-WM_probseg.nii.gz', label='WM'),
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
    collected = collect_derivatives('/mock/derivs', '01', [], spec=spec, patterns={})
    assert collected['t1w_tpms'] == [
        '/mock/label-GM_probseg.nii.gz',
        '/mock/label-WM_probseg.nii.gz',
        '/mock/label-CSF_probseg.nii.gz',
    ]

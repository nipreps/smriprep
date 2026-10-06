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

from smriprep.utils.bids import collect_anat_derivatives

from . import deriv_skeleton

IMAGES = ['t1w_preproc', 't2w_preproc', 'mask', 'dseg', 'tpms', 'ribbon']
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
    'cortex',
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
    assert len(deriv_skeleton(['tpms'])['01'][0]['anat']) == 3
    # 2 TPMs + 1 mask
    partial = deriv_skeleton({'tpms': 2, 'mask': True, 'dseg': False})
    assert len(partial['01'][0]['anat']) == 3

    with_session = deriv_skeleton(['mask'], subject='02', session='A')
    assert with_session['02'] == [{'session': 'A', 'anat': [{'suffix': 'mask', 'desc': 'brain'}]}]

    with pytest.raises(KeyError, match='masque'):
        deriv_skeleton(['masque'])


def test_collect_anat_derivatives(deriv_dset):
    collected = collect_anat_derivatives([deriv_dset()], '01', ['MNI152NLin2009cAsym'])

    assert sorted(collected) == ['images', 'surfaces', 'transforms']
    assert sorted(collected['images']) == sorted(IMAGES)
    assert sorted(collected['surfaces']) == sorted(SURFACES)
    tpms = collected['images']['tpms']
    assert [_entity(path, 'label') for path in tpms] == ['GM', 'WM', 'CSF']
    for surface in SURFACES:
        assert [_entity(path, 'hemi') for path in collected['surfaces'][surface]] == ['L', 'R']

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
        ({'tpms': 2}, 'tpms'),
        ({'white': 1}, 'white'),
        ({'sphere_reg_msm': 1}, 'sphere_reg_msm'),
        ({'cortex': 1}, 'cortex'),
    ],
)
def test_collect_anat_derivatives_incomplete(deriv_dset, include, key):
    """A multi-file derivative with missing files is not collected."""
    collected = collect_anat_derivatives([deriv_dset(include)], '01', [])
    assert key not in collected['images'] | collected['surfaces']


def test_collect_anat_derivatives_one_direction(deriv_dset):
    deriv_dir = deriv_dset({'xfm_MNI152NLin2009cAsym': 1})
    collected = collect_anat_derivatives([deriv_dir], '01', ['MNI152NLin2009cAsym'])
    assert sorted(collected['transforms']['MNI152NLin2009cAsym']) == ['forward']


def test_collect_anat_derivatives_session(deriv_dset):
    deriv_dir = deriv_dset(['mask'], session='A')

    collected = collect_anat_derivatives([deriv_dir], '01', [], session_id='A')
    assert _entity(collected['images']['mask'], 'ses') == 'A'

    collected = collect_anat_derivatives([deriv_dir], '01', [], session_id='B')
    assert _paths(collected) == []


def test_collect_anat_derivatives_any_session(deriv_dset):
    """Without a session label, derivatives under any session are found."""
    deriv_dir = deriv_dset(['mask'], session='A')
    collected = collect_anat_derivatives([deriv_dir], '01', [])
    assert _entity(collected['images']['mask'], 'ses') == 'A'


def test_collect_anat_derivatives_ambiguous(tmp_path):
    """Derivatives from several sessions, without a session label, are an error."""
    skeleton = deriv_skeleton(['mask'], session='A')
    skeleton['01'] += deriv_skeleton(['mask'], session='B')['01']
    deriv_dir = tmp_path / 'derivatives'
    generate_bids_skeleton(deriv_dir, skeleton)

    with pytest.raises(ValueError, match='expected at most one match'):
        collect_anat_derivatives([deriv_dir], '01', [])


def test_collect_anat_derivatives_subject(deriv_dset):
    deriv_dir = deriv_dset(['mask'])
    assert _paths(collect_anat_derivatives([deriv_dir], '02', [])) == []


def test_collect_anat_derivatives_multiple_datasets(deriv_dset):
    """Derivatives are merged across datasets, with later datasets taking precedence."""
    first = deriv_dset(['mask', 'dseg', 'white', 'xfm_MNI152NLin2009cAsym'], name='first')
    second = deriv_dset(['mask', 'pial', 'xfm_fsnative'], name='second')

    collected = collect_anat_derivatives([first, second], '01', ['MNI152NLin2009cAsym'])

    assert collected['images']['dseg'].startswith(str(first))
    assert collected['images']['mask'].startswith(str(second))
    assert 'white' in collected['surfaces']
    assert 'pial' in collected['surfaces']

    xfms = collected['transforms']
    assert xfms['MNI152NLin2009cAsym']['forward'].startswith(str(first))
    assert xfms['fsnative']['reverse'].startswith(str(second))


def test_collect_anat_derivatives_split_transform_pair(deriv_dset):
    """A forward and reverse transform from different datasets are not combined."""
    first = deriv_dset({'xfm_MNI152NLin2009cAsym': 1}, name='first')  # forward only
    second = deriv_dset(['xfm_MNI152NLin2009cAsym'], name='second')
    # Leave only the reverse transform in the second dataset
    for path in (second / 'sub-01' / 'anat').glob('*_from-T1w_*'):
        path.unlink()

    collected = collect_anat_derivatives([first, second], '01', ['MNI152NLin2009cAsym'])

    xfms = collected['transforms']['MNI152NLin2009cAsym']
    assert 'forward' not in xfms
    assert xfms['reverse'].startswith(str(second))


LEGACY_SPHERE_REG = [{'hemi': hemi, 'desc': 'reg'} for hemi in ('L', 'R')]
FSAVERAGE_SPHERE_REG = [{'hemi': hemi, 'space': 'fsaverage', 'desc': 'reg'} for hemi in ('L', 'R')]


def _sphere_reg_dset(deriv_dir, entities):
    """Write a derivatives dataset containing only the given registration spheres."""
    files = [{'suffix': 'sphere', 'extension': '.surf.gii', **ents} for ents in entities]
    generate_bids_skeleton(deriv_dir, {'01': [{'anat': files}]})
    return deriv_dir


@pytest.mark.parametrize(
    ('sphere_reg_entities', 'expected', 'warns'),
    [
        pytest.param(LEGACY_SPHERE_REG, [None, None], True, id='without-fsaverage'),
        pytest.param(FSAVERAGE_SPHERE_REG, ['fsaverage', 'fsaverage'], False, id='with-fsaverage'),
        # Current naming takes precedence over legacy naming
        pytest.param(
            LEGACY_SPHERE_REG + FSAVERAGE_SPHERE_REG,
            ['fsaverage', 'fsaverage'],
            False,
            id='both',
        ),
    ],
)
def test_collect_anat_derivatives_reuses_sphere_reg(
    tmp_path, caplog, sphere_reg_entities, expected, warns
):
    """The fsaverage sphere is reusable under either naming convention, preferring the
    current one.
    """
    deriv_dir = _sphere_reg_dset(tmp_path / 'derivatives', sphere_reg_entities)

    with caplog.at_level(logging.WARNING, logger='nipype.workflow'):
        collected = collect_anat_derivatives([deriv_dir], '01', [])

    spheres = collected['surfaces'].get('sphere_reg')
    assert ([_entity(path, 'space') for path in spheres] if spheres else None) == expected
    assert any('legacy sphere_reg' in record.message for record in caplog.records) is warns


def test_collect_anat_derivatives_sphere_reg_later_dataset(tmp_path, caplog):
    """A later dataset's fsaverage sphere replaces an earlier legacy one."""
    first = _sphere_reg_dset(tmp_path / 'first', LEGACY_SPHERE_REG)
    second = _sphere_reg_dset(tmp_path / 'second', FSAVERAGE_SPHERE_REG)

    with caplog.at_level(logging.WARNING, logger='nipype.workflow'):
        collected = collect_anat_derivatives([first, second], '01', [])

    spheres = collected['surfaces']['sphere_reg']
    assert [_entity(path, 'space') for path in spheres] == ['fsaverage', 'fsaverage']
    assert all(path.startswith(str(second)) for path in spheres)
    # The overridden legacy sphere is not used, so it is not reported
    assert not any('legacy sphere_reg' in record.message for record in caplog.records)


def test_collect_anat_derivatives_sphere_reg_incomplete_fsaverage(tmp_path):
    """One fsaverage hemisphere prevents reuse, even next to complete legacy files."""
    deriv_dir = _sphere_reg_dset(
        tmp_path / 'derivatives', LEGACY_SPHERE_REG + FSAVERAGE_SPHERE_REG[:1]
    )
    assert collect_anat_derivatives([deriv_dir], '01', [])['surfaces'].get('sphere_reg') is None


def test_collect_anat_derivatives_transforms(deriv_dset):
    """Ensure transforms are collected for the right spaces."""
    output_spaces = ['MNI152NLin2009cAsym', 'MNIPediatricAsym:cohort-3']
    collected = collect_anat_derivatives([deriv_dset()], '01', output_spaces)
    xfms = collected['transforms']
    for space in output_spaces:
        template = space.replace(':cohort-', '+')
        assert _entity(xfms[space]['reverse'], 'from') == template
        assert _entity(xfms[space]['forward'], 'to') == template

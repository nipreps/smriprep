import logging

import pytest
from niworkflows.utils.testing import generate_bids_skeleton

from ..bids import collect_derivatives
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


@pytest.mark.parametrize(
    ('sphere_reg_entities', 'warns'),
    [
        pytest.param({'desc': 'reg'}, True, id='without-fsaverage'),
        pytest.param({'space': 'fsaverage', 'desc': 'reg'}, False, id='with-fsaverage'),
    ],
)
def test_collect_derivatives_reuses_sphere_reg(tmp_path, caplog, sphere_reg_entities, warns):
    """The fsaverage registration sphere is reusable under both naming conventions."""
    skeleton = {
        '01': [
            {
                'anat': [
                    {
                        'suffix': 'sphere',
                        'hemi': hemi,
                        'extension': '.surf.gii',
                        **sphere_reg_entities,
                    }
                    for hemi in ('L', 'R')
                ]
            }
        ]
    }
    deriv_dir = tmp_path / 'derivatives'
    generate_bids_skeleton(deriv_dir, skeleton)

    with caplog.at_level(logging.WARNING, logger='nipype.workflow'):
        collected = collect_derivatives(deriv_dir, '01', [])

    assert len(collected['sphere_reg']) == 2
    assert any('legacy sphere_reg' in record.message for record in caplog.records) is warns


def test_collect_derivatives_transforms(deriv_dset):
    """Ensure transforms are collected for the right spaces."""
    output_spaces = ['MNI152NLin2009cAsym', 'MNIPediatricAsym:cohort-3']
    collected = collect_derivatives(deriv_dset, '01', output_spaces)
    xfms = collected['transforms']
    for space in output_spaces:
        template = space.split(':')[0]
        assert template in xfms[space]['reverse']
        assert template in xfms[space]['forward']

from niworkflows.utils.testing import generate_bids_skeleton

from ..bids import collect_derivatives
from . import DERIV_SKELETON


def test_collect_derivatives(tmp_path):
    deriv_dir = tmp_path / 'derivatives'
    generate_bids_skeleton(deriv_dir, str(DERIV_SKELETON))
    output_spaces = ['MNI152NLin2009cAsym', 'MNIPediatricAsym:cohort-3']
    collected = collect_derivatives(deriv_dir, '01', output_spaces)
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

from pathlib import Path

import nibabel as nb
import numpy as np
import pytest
from nipype.pipeline.engine.utils import generate_expanded_graph
from niworkflows.utils.spaces import Reference, SpatialReferences
from niworkflows.utils.testing import generate_bids_skeleton

from ..anatomical import init_anat_fit_wf, init_anat_preproc_wf

BASE_LAYOUT = {
    '01': {
        'anat': [
            {'run': 1, 'suffix': 'T1w'},
            {'run': 2, 'suffix': 'T1w'},
            {'suffix': 'T2w'},
        ],
        'func': [
            {
                'task': 'rest',
                'run': i,
                'suffix': 'bold',
                'metadata': {'PhaseEncodingDirection': 'j', 'TotalReadoutTime': 0.6},
            }
            for i in range(1, 3)
        ],
        'fmap': [
            {'suffix': 'phasediff', 'metadata': {'EchoTime1': 0.005, 'EchoTime2': 0.007}},
            {'suffix': 'magnitude1', 'metadata': {'EchoTime': 0.005}},
            {
                'suffix': 'epi',
                'direction': 'PA',
                'metadata': {'PhaseEncodingDirection': 'j', 'TotalReadoutTime': 0.6},
            },
            {
                'suffix': 'epi',
                'direction': 'AP',
                'metadata': {'PhaseEncodingDirection': 'j-', 'TotalReadoutTime': 0.6},
            },
        ],
    },
}


@pytest.fixture(scope='module', autouse=True)
def _quiet_logger():
    import logging

    logger = logging.getLogger('nipype.workflow')
    old_level = logger.getEffectiveLevel()
    logger.setLevel(logging.ERROR)
    yield
    logger.setLevel(old_level)


@pytest.fixture(scope='module')
def bids_root(tmp_path_factory):
    base = tmp_path_factory.mktemp('base')
    bids_dir = base / 'bids'
    generate_bids_skeleton(bids_dir, BASE_LAYOUT)
    return bids_dir


@pytest.mark.parametrize('freesurfer', [True, False])
@pytest.mark.parametrize('cifti_output', [False, '91k'])
def test_init_anat_preproc_wf(
    bids_root: Path,
    tmp_path: Path,
    freesurfer: bool,
    cifti_output: bool,
):
    output_dir = tmp_path / 'output'
    output_dir.mkdir()

    init_anat_preproc_wf(
        bids_root=str(bids_root),
        output_dir=str(output_dir),
        freesurfer=freesurfer,
        hires=False,
        longitudinal=False,
        msm_sulc=False,
        t1w=[str(bids_root / 'sub-01' / 'anat' / 'sub-01_T1w.nii.gz')],
        t2w=[str(bids_root / 'sub-01' / 'anat' / 'sub-01_T2w.nii.gz')],
        skull_strip_mode='force',
        skull_strip_template=Reference('OASIS30ANTs'),
        spaces=SpatialReferences(
            spaces=['MNI152NLin2009cAsym', 'fsaverage5'],
            checkpoint=True,
        ),
        precomputed={},
        omp_nthreads=1,
        cifti_output=cifti_output,
    )


@pytest.mark.parametrize('msm_sulc', [True, False])
@pytest.mark.parametrize('skull_strip_mode', ['skip', 'force'])
def test_anat_fit_wf(
    bids_root: Path,
    tmp_path: Path,
    msm_sulc: bool,
    skull_strip_mode: str,
):
    output_dir = tmp_path / 'output'
    output_dir.mkdir()

    init_anat_fit_wf(
        bids_root=str(bids_root),
        output_dir=str(output_dir),
        freesurfer=True,
        hires=False,
        longitudinal=False,
        msm_sulc=msm_sulc,
        t1w=[str(bids_root / 'sub-01' / 'anat' / 'sub-01_T1w.nii.gz')],
        t2w=[str(bids_root / 'sub-01' / 'anat' / 'sub-01_T2w.nii.gz')],
        skull_strip_mode=skull_strip_mode,
        skull_strip_template=Reference('OASIS30ANTs'),
        spaces=SpatialReferences(
            spaces=['MNI152NLin2009cAsym', 'fsaverage5'],
            checkpoint=True,
        ),
        precomputed={},
        omp_nthreads=1,
    )


@pytest.mark.parametrize('t1w', [1, 2])
@pytest.mark.parametrize('t2w', [0, 1])
@pytest.mark.parametrize('skull_strip_mode', ['skip', 'force'])
@pytest.mark.parametrize('t1w_preproc', [False, True])
@pytest.mark.parametrize('t2w_preproc', [False, True])
@pytest.mark.parametrize('t1w_mask', [False, True])
@pytest.mark.parametrize('t1w_dseg', [False, True])
@pytest.mark.parametrize('t1w_tpms', [False, True])
@pytest.mark.parametrize('xfms', [False, True])
@pytest.mark.parametrize('sphere_reg_msm', [0, 1, 2])
def test_anat_fit_precomputes(
    bids_root: Path,
    tmp_path: Path,
    t1w: int,
    t2w: int,
    skull_strip_mode: str,
    t1w_preproc: bool,
    t2w_preproc: bool,
    t1w_mask: bool,
    t1w_dseg: bool,
    t1w_tpms: bool,
    xfms: bool,
    sphere_reg_msm: int,
):
    """Test as many combinations of precomputed files and input
    configurations as possible."""
    output_dir = tmp_path / 'output'
    output_dir.mkdir()

    # Construct inputs
    t1w_list = [
        str(bids_root / 'sub-01' / 'anat' / 'sub-01_run-1_T1w.nii.gz'),
        str(bids_root / 'sub-01' / 'anat' / 'sub-01_run-2_T1w.nii.gz'),
    ][:t1w]
    t2w_list = [str(bids_root / 'sub-01' / 'anat' / 'sub-01_T2w.nii.gz')][:t2w]

    # Construct precomputed files
    empty_img = nb.Nifti1Image(np.zeros((1, 1, 1)), np.eye(4))
    precomputed = {}
    if t1w_preproc:
        precomputed['t1w_preproc'] = str(tmp_path / 't1w_preproc.nii.gz')
    if t2w_preproc:
        precomputed['t2w_preproc'] = str(tmp_path / 't2w_preproc.nii.gz')
    if t1w_mask:
        precomputed['t1w_mask'] = str(tmp_path / 't1w_mask.nii.gz')
    if t1w_dseg:
        precomputed['t1w_dseg'] = str(tmp_path / 't1w_dseg.nii.gz')
    if t1w_tpms:
        precomputed['t1w_tpms'] = str(tmp_path / 't1w_tpms.nii.gz')

    for path in precomputed.values():
        empty_img.to_filename(path)

    precomputed['sphere_reg_msm'] = [
        str(tmp_path / f'sub-01_hemi-{hemi}_desc-msm_sphere.surf.gii') for hemi in ['L', 'R']
    ][:sphere_reg_msm]
    for path in precomputed['sphere_reg_msm']:
        Path(path).touch()

    if xfms:
        transforms = precomputed['transforms'] = {}
        transforms['MNI152NLin2009cAsym'] = {
            'forward': str(tmp_path / 'MNI152NLin2009cAsym_forward_xfm.txt'),
            'reverse': str(tmp_path / 'MNI152NLin2009cAsym_reverse_xfm.txt'),
        }
        transforms['fsnative'] = {
            'forward': str(tmp_path / 'fsnative_forward_xfm.txt'),
            'reverse': str(tmp_path / 'fsnative_reverse_xfm.txt'),
        }

        # Write dummy transforms
        for xfm in transforms.values():
            for path in xfm.values():
                Path(path).touch()

    # Create workflow
    wf = init_anat_fit_wf(
        bids_root=str(bids_root),
        output_dir=str(output_dir),
        freesurfer=True,
        hires=False,
        longitudinal=False,
        msm_sulc=True,
        t1w=t1w_list,
        t2w=t2w_list,
        skull_strip_mode=skull_strip_mode,
        skull_strip_template=Reference('OASIS30ANTs'),
        spaces=SpatialReferences(
            spaces=['MNI152NLin2009cAsym', 'fsaverage5'],
            checkpoint=True,
        ),
        precomputed=precomputed,
        omp_nthreads=1,
    )

    flatgraph = wf._create_flat_graph()
    generate_expanded_graph(flatgraph)

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
from nipype.pipeline.engine.utils import generate_expanded_graph
from niworkflows.utils.spaces import Reference, SpatialReferences
from niworkflows.utils.testing import generate_bids_skeleton

from smriprep.utils.bids import collect_anat_derivatives
from smriprep.workflows.anatomical import init_anat_fit_wf, init_anat_preproc_wf

from ..utils import DERIV_GROUPS

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
@pytest.mark.parametrize('include', [None, *DERIV_GROUPS])
def test_anat_fit_precomputes(
    bids_root: Path,
    tmp_path: Path,
    deriv_dset,
    t1w: int,
    t2w: int,
    skull_strip_mode: str,
    include: str | None,
):
    """Test precomputed inputs one-by-one with a few input configurations."""
    output_dir = tmp_path / 'output'
    output_dir.mkdir()

    # Construct inputs
    t1w_list = [
        str(bids_root / 'sub-01' / 'anat' / 'sub-01_run-1_T1w.nii.gz'),
        str(bids_root / 'sub-01' / 'anat' / 'sub-01_run-2_T1w.nii.gz'),
    ][:t1w]
    t2w_list = [str(bids_root / 'sub-01' / 'anat' / 'sub-01_T2w.nii.gz')][:t2w]

    # Collect precomputed files from a derivatives dataset
    deriv_dir = deriv_dset([include] if include else [])
    precomputed = collect_anat_derivatives([deriv_dir], '01', ['MNI152NLin2009cAsym'])

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


@pytest.mark.parametrize('omit', [None, *DERIV_GROUPS])
def test_anat_fit_precomputes_omit_one(
    bids_root: Path,
    tmp_path: Path,
    deriv_dset,
    omit: str | None,
):
    """Build the fit workflow from a complete set of derivatives, less at most one."""
    output_dir = tmp_path / 'output'
    output_dir.mkdir()

    deriv_dir = deriv_dset([group for group in DERIV_GROUPS if group != omit])
    precomputed = collect_anat_derivatives([deriv_dir], '01', ['MNI152NLin2009cAsym'])

    collected = {*precomputed['images'], *precomputed['surfaces']}
    # Spaces without transforms are left out entirely
    collected.update(f'xfm_{space}' for space in precomputed['transforms'])
    # Transforms are only collected for requested spaces
    assert collected == set(DERIV_GROUPS) - {omit, 'xfm_MNIPediatricAsym+3'}

    wf = init_anat_fit_wf(
        bids_root=str(bids_root),
        output_dir=str(output_dir),
        freesurfer=True,
        hires=False,
        longitudinal=False,
        msm_sulc=True,
        t1w=[str(bids_root / 'sub-01' / 'anat' / 'sub-01_run-1_T1w.nii.gz')],
        t2w=[str(bids_root / 'sub-01' / 'anat' / 'sub-01_T2w.nii.gz')],
        skull_strip_mode='force',
        skull_strip_template=Reference('OASIS30ANTs'),
        spaces=SpatialReferences(
            spaces=['MNI152NLin2009cAsym', 'fsaverage5'],
            checkpoint=True,
        ),
        precomputed=precomputed,
        omp_nthreads=1,
    )

    # Without a precomputed fsnative transform, surface reconstruction estimates one
    estimated = wf.get_node('surface_recon_wf.fsnative2t1w_xfm') is not None
    assert estimated is (omit == 'xfm_fsnative')

    flatgraph = wf._create_flat_graph()
    generate_expanded_graph(flatgraph)


def test_anat_fit_precomputes_fsnative_forward_only(
    bids_root: Path,
    tmp_path: Path,
    deriv_dset,
):
    """A T1w-to-fsnative transform without its reverse is not silently used."""
    output_dir = tmp_path / 'output'
    output_dir.mkdir()

    deriv_dir = deriv_dset({'xfm_fsnative': 1})  # forward (T1w-to-fsnative) only
    precomputed = collect_anat_derivatives([deriv_dir], '01', ['MNI152NLin2009cAsym'])
    assert sorted(precomputed['transforms']['fsnative']) == ['forward']

    with pytest.raises(RuntimeError, match='without the reverse'):
        init_anat_fit_wf(
            bids_root=str(bids_root),
            output_dir=str(output_dir),
            freesurfer=True,
            hires=False,
            longitudinal=False,
            msm_sulc=True,
            t1w=[str(bids_root / 'sub-01' / 'anat' / 'sub-01_run-1_T1w.nii.gz')],
            t2w=[],
            skull_strip_mode='force',
            skull_strip_template=Reference('OASIS30ANTs'),
            spaces=SpatialReferences(
                spaces=['MNI152NLin2009cAsym', 'fsaverage5'],
                checkpoint=True,
            ),
            precomputed=precomputed,
            omp_nthreads=1,
        )


def _init_fit_wf(bids_root: Path, tmp_path: Path, precomputed: dict):
    """Build the anatomical fit workflow from one T1w and the given derivatives."""
    output_dir = tmp_path / 'output'
    output_dir.mkdir(exist_ok=True)
    return init_anat_fit_wf(
        bids_root=str(bids_root),
        output_dir=str(output_dir),
        freesurfer=True,
        hires=False,
        longitudinal=False,
        msm_sulc=True,
        t1w=[str(bids_root / 'sub-01' / 'anat' / 'sub-01_run-1_T1w.nii.gz')],
        t2w=[],
        skull_strip_mode='force',
        skull_strip_template=Reference('OASIS30ANTs'),
        spaces=SpatialReferences(
            spaces=['MNI152NLin2009cAsym', 'fsaverage5'],
            checkpoint=True,
        ),
        precomputed=precomputed,
        omp_nthreads=1,
    )


def test_anat_fit_reports_precomputed(bids_root: Path, tmp_path: Path, deriv_dset, caplog):
    """Building the fit workflow reports every precomputed derivative found."""
    precomputed = collect_anat_derivatives([deriv_dset()], '01', ['MNI152NLin2009cAsym'])

    with caplog.at_level(logging.INFO, logger='nipype.workflow'):
        _init_fit_wf(bids_root, tmp_path, precomputed)

    reports = [
        record.getMessage()
        for record in caplog.records
        if record.getMessage().startswith('ANAT Found precomputed derivatives:')
    ]
    assert len(reports) == 1
    paths = [
        path
        for kind in ('images', 'surfaces')
        for value in precomputed[kind].values()
        for path in ([value] if isinstance(value, str) else value)
    ]
    paths.extend(path for xfms in precomputed['transforms'].values() for path in xfms.values())
    # Every file in the skeleton, except the transforms for an unrequested space
    assert len(paths) == 34
    for path in paths:
        assert path in reports[0]


@pytest.mark.parametrize('legacy', [False, True])
def test_anat_fit_warns_legacy_sphere_reg(
    bids_root: Path, tmp_path: Path, deriv_dset, caplog, legacy: bool
):
    """A sphere_reg without a space entity warns about deprecated naming."""
    deriv_dir = deriv_dset()
    if legacy:
        anat_dir = deriv_dir / 'sub-01' / 'anat'
        for path in anat_dir.glob('*_space-fsaverage_desc-reg_sphere.surf.gii'):
            path.rename(path.with_name(path.name.replace('_space-fsaverage', '')))
    precomputed = collect_anat_derivatives([deriv_dir], '01', ['MNI152NLin2009cAsym'])
    assert len(precomputed['surfaces']['sphere_reg']) == 2

    with caplog.at_level(logging.WARNING, logger='nipype.workflow'):
        _init_fit_wf(bids_root, tmp_path, precomputed)

    warnings = [r.getMessage() for r in caplog.records if 'legacy sphere_reg' in r.getMessage()]
    assert len(warnings) == int(legacy)

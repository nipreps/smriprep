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
"""Tests for outputs workflow helpers."""

import json
from pathlib import Path

import nibabel as nb
import numpy as np
import pytest
from nipype.interfaces.base import Undefined

from smriprep.workflows.outputs import (
    _bids_relative,
    _combine_cohort,
    _drop_cohort,
    _drop_path,
    _empty_report,
    _fmt_cohort,
    _gen_full_space,
    _is_native,
    _no_native,
    _pick_cohort,
    _pop,
    _read_json,
    _rpt_masks,
    init_ds_anat_volumes_wf,
    init_ds_dseg_wf,
    init_ds_fs_registration_wf,
    init_ds_fs_segs_wf,
    init_ds_grayord_metrics_wf,
    init_ds_mask_wf,
    init_ds_surface_masks_wf,
    init_ds_surface_metrics_wf,
    init_ds_surfaces_wf,
    init_ds_template_registration_wf,
    init_ds_template_wf,
    init_ds_tpms_wf,
    init_template_iterator_wf,
)


def test_outputs_helper_cohort_parsers():
    assert _drop_cohort('MNIPediatricAsym:cohort-2') == 'MNIPediatricAsym'
    assert _drop_cohort(['MNI152NLin6Asym', 'MNIPediatricAsym:cohort-2']) == [
        'MNI152NLin6Asym',
        'MNIPediatricAsym',
    ]
    assert _pick_cohort('MNIPediatricAsym:cohort-2') == '2'
    assert _pick_cohort('MNI152NLin6Asym') is Undefined
    assert _combine_cohort('MNIPediatricAsym:cohort-2:res-1') == 'MNIPediatricAsym+2'
    assert _combine_cohort(['MNI152NLin6Asym', 'MNIPediatricAsym:cohort-2']) == [
        'MNI152NLin6Asym',
        'MNIPediatricAsym+2',
    ]


def test_outputs_helper_simple_values(monkeypatch, tmp_path):
    assert _is_native('native') is True
    assert _is_native('1') is False
    assert _no_native(3) == 3
    assert _no_native('native') == 1
    assert _no_native('native', sloppy=True) == 2
    assert _fmt_cohort('MNIPediatricAsym', cohort='2') == 'MNIPediatricAsym:cohort-2'
    assert _fmt_cohort('MNI152NLin6Asym') == 'MNI152NLin6Asym'
    assert _gen_full_space('MNIPediatricAsym', cohort='2') == 'MNIPediatricAsym+2'
    assert _gen_full_space('MNI152NLin6Asym') == 'MNI152NLin6Asym'
    assert _pop(['a', 'b']) == 'a'

    import templateflow.conf as tf_conf

    monkeypatch.setattr(tf_conf, 'TF_HOME', tmp_path)
    sample = tmp_path / 'tpl-test' / 'file.nii.gz'
    sample.parent.mkdir(parents=True)
    sample.write_text('x')
    assert _drop_path(str(sample)) == 'tpl-test/file.nii.gz'


def test_outputs_helper_empty_and_read_json(tmp_path, monkeypatch):
    infile = tmp_path / 'existing.html'
    infile.write_text('<p>x</p>')
    assert _empty_report(str(infile)) == str(infile)

    monkeypatch.chdir(tmp_path)
    out = Path(_empty_report())
    assert out.exists()
    assert 'previously computed T1w template' in out.read_text()

    payload = {'a': 1}
    json_file = tmp_path / 'meta.json'
    json_file.write_text(json.dumps(payload))
    assert _read_json(str(json_file)) == payload


def test_rpt_masks(make_nifti, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mask_file = make_nifti(
        tmp_path / 'mask.nii.gz', data=np.array([[[1, 0], [1, 0]]], dtype='uint8')
    )
    before = make_nifti(
        tmp_path / 'before.nii.gz', data=np.array([[[2, 2], [2, 2]]], dtype='float32')
    )
    after = make_nifti(
        tmp_path / 'after.nii.gz', data=np.array([[[3, 3], [3, 3]]], dtype='float32')
    )
    after_mask = make_nifti(
        tmp_path / 'after_mask.nii.gz', data=np.array([[[1, 1], [0, 0]]], dtype='uint8')
    )

    out_before, out_after = _rpt_masks(mask_file, before, after, after_mask=after_mask)
    before_data = np.asanyarray(nb.load(out_before).dataobj)
    after_data = np.asanyarray(nb.load(out_after).dataobj)
    assert np.array_equal(before_data, np.array([[[2, 0], [2, 0]]], dtype='float32'))
    assert np.array_equal(after_data, np.array([[[3, 3], [0, 0]]], dtype='float32'))


@pytest.mark.xfail(
    strict=True,
    reason='Known bug: _bids_relative computes relative paths but returns original inputs.',
)
def test_bids_relative_expected_relative_paths(tmp_path):
    bids_root = tmp_path / 'bids'
    anat_file = bids_root / 'sub-01' / 'anat' / 'sub-01_T1w.nii.gz'
    anat_file.parent.mkdir(parents=True)
    anat_file.write_text('x')
    assert _bids_relative([str(anat_file)], str(bids_root)) == ['sub-01/anat/sub-01_T1w.nii.gz']


@pytest.mark.parametrize('num_anat', [1, 2])
def test_init_ds_template_wf(num_anat):
    wf = init_ds_template_wf(num_anat=num_anat, output_dir='.', image_type='T1w')
    names = {node.name for node in wf._get_all_nodes()}
    assert 'ds_anat_preproc' in names
    assert ('ds_anat_ref_xfms' in names) == (num_anat > 1)


@pytest.mark.parametrize(
    ('mask_type', 'expected_type'),
    [
        ('brain', 'Brain'),
        ('roi', 'ROI'),
        ('ribbon', 'ROI'),
    ],
)
def test_init_ds_mask_wf(mask_type, expected_type):
    wf = init_ds_mask_wf(bids_root='.', output_dir='.', mask_type=mask_type)
    assert wf.get_node('ds_anat_mask').inputs.Type == expected_type


def test_init_outputs_workflow_smoke(monkeypatch):
    wf_dseg = init_ds_dseg_wf(output_dir='.')
    wf_tpms = init_ds_tpms_wf(output_dir='.')
    wf_treg = init_ds_template_registration_wf(output_dir='.', image_type='T1w')
    wf_fsreg = init_ds_fs_registration_wf(output_dir='.', image_type='T1w')
    wf_surf = init_ds_surfaces_wf(
        output_dir='.',
        surfaces=['sphere_reg', 'sphere_reg_fsLR', 'sphere_reg_msm'],
    )
    wf_metrics = init_ds_surface_metrics_wf(
        bids_root='.', output_dir='.', metrics=['curv', 'sulc']
    )
    wf_grayord = init_ds_grayord_metrics_wf(
        bids_root='.',
        output_dir='.',
        metrics=['curv'],
        cifti_output='91k',
    )
    wf_vol = init_ds_anat_volumes_wf(bids_root='.', output_dir='.')
    wf_fssegs = init_ds_fs_segs_wf(bids_root='.', output_dir='.')
    wf_smask = init_ds_surface_masks_wf(output_dir='.', mask_type='brain')

    assert wf_tpms.get_node('ds_anat_tpms').inputs.label == ('GM', 'WM', 'CSF')
    assert 'lta2itk' in {n.name for n in wf_fsreg._get_all_nodes()}
    assert wf_surf.get_node('ds_sphere_reg').inputs.space == 'fsaverage'
    assert wf_surf.get_node('ds_sphere_reg_fsLR').inputs.space == 'fsLR'
    assert wf_surf.get_node('ds_sphere_reg_msm').inputs.desc == 'msmsulc'
    assert 'ds_curv' in {n.name for n in wf_metrics._get_all_nodes()}
    assert 'ds_curv' in {n.name for n in wf_grayord._get_all_nodes()}
    assert 'anat2std_t1w' in {n.name for n in wf_vol._get_all_nodes()}
    assert 'ds_anat_fsaseg' in {n.name for n in wf_fssegs._get_all_nodes()}
    assert 'ds_surf_mask' in {n.name for n in wf_smask._get_all_nodes()}
    assert 'ds_std2anat_xfm' in {n.name for n in wf_treg._get_all_nodes()}
    assert 'ds_anat_dseg' in {n.name for n in wf_dseg._get_all_nodes()}

    class _SpaceRef:
        def __init__(self, fullname, spec):
            self.fullname = fullname
            self.spec = spec

    class _SpaceCache:
        def get_standard(self, dim=(3,)):
            return [_SpaceRef('MNI152NLin2009cAsym', {'resolution': 1})]

    class _Spaces:
        cached = _SpaceCache()

        def get_spaces(self, nonstandard=False, dim=(3,)):
            return ['MNI152NLin2009cAsym']

    monkeypatch.setattr(
        'smriprep.workflows.outputs.fetch_template_files',
        lambda template, specs=None, sloppy=False: {'t1w': 'x', 'mask': 'y', 't2w': Undefined},
    )
    template_iter = init_template_iterator_wf(spaces=_Spaces())
    assert {'select_tpl', 'select_xfm', 'spacesource'} <= {
        node.name for node in template_iter._get_all_nodes()
    }

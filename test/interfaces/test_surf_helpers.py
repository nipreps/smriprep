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
"""Tests for surface helper utilities."""

import nibabel as nb
import numpy as np

from smriprep.interfaces.surf import (
    AggregateSurfaces,
    fix_gifti_metadata,
    make_ribbon,
    normalize_surfs,
)


def test_normalize_surfs_graymid_to_midthickness(make_gifti_surface, tmp_path):
    in_file = make_gifti_surface(
        tmp_path / 'lh.graymid.surf.gii',
        meta={
            'GeometricType': 'Anatomical',
            'VolGeomX_R': '1',
            'VolGeomY_A': '2',
        },
    )
    out_file = normalize_surfs(in_file, transform_file=None, newpath=str(tmp_path))
    assert out_file.endswith('lh.midthickness.surf.gii')

    pointset = nb.load(out_file).get_arrays_from_intent('NIFTI_INTENT_POINTSET')[0]
    assert pointset.meta['AnatomicalStructureSecondary'] == 'MidThickness'
    assert pointset.meta['GeometricType'] == 'Anatomical'
    assert 'VolGeomX_R' not in pointset.meta
    assert 'VolGeomY_A' not in pointset.meta


def test_normalize_surfs_fixes_sphere_metadata(make_gifti_surface, tmp_path):
    in_file = make_gifti_surface(
        tmp_path / 'lh.sphere.reg.surf.gii',
        meta={'GeometricType': 'Sphere', 'VolGeomX_R': '1'},
    )
    out_file = normalize_surfs(in_file, transform_file=None, newpath=str(tmp_path))
    pointset = nb.load(out_file).get_arrays_from_intent('NIFTI_INTENT_POINTSET')[0]
    assert pointset.meta['GeometricType'] == 'Spherical'
    assert pointset.meta['VolGeomX_R'] == '1'


def test_fix_gifti_metadata(make_gifti_surface, tmp_path):
    in_file = make_gifti_surface(
        tmp_path / 'lh.sphere.reg.surf.gii', meta={'GeometricType': 'Sphere'}
    )
    out_file = fix_gifti_metadata(in_file, newpath=str(tmp_path))
    pointset = nb.load(out_file).get_arrays_from_intent('NIFTI_INTENT_POINTSET')[0]
    assert pointset.meta['GeometricType'] == 'Spherical'


def test_aggregate_surfaces_groups_pairs(tmp_path):
    files = []
    for name in (
        'sub-01_hemi-L_white.surf.gii',
        'sub-01_hemi-R_white.surf.gii',
        'sub-01_hemi-L_pial.surf.gii',
        'sub-01_hemi-R_pial.surf.gii',
        'sub-01_hemi-L_thickness.shape.gii',
        'sub-01_hemi-R_thickness.shape.gii',
    ):
        path = tmp_path / name
        path.write_text('x')
        files.append(str(path))

    result = AggregateSurfaces(
        surfaces=[f for f in files if 'surf.gii' in f],
        morphometrics=[f for f in files if 'shape.gii' in f],
    ).run(cwd=tmp_path)
    assert len(result.outputs.white) == 2
    assert len(result.outputs.pial) == 2
    assert len(result.outputs.thickness) == 2


def test_make_ribbon_small_volumes(make_nifti, tmp_path):
    white = [
        make_nifti(
            tmp_path / 'lh.white.nii.gz', data=np.array([[[1, 1], [0, 0]]], dtype='float32')
        ),
        make_nifti(
            tmp_path / 'rh.white.nii.gz', data=np.array([[[0, 1], [1, 0]]], dtype='float32')
        ),
    ]
    pial = [
        make_nifti(
            tmp_path / 'lh.pial.nii.gz', data=np.array([[[-1, 1], [-1, 1]]], dtype='float32')
        ),
        make_nifti(
            tmp_path / 'rh.pial.nii.gz', data=np.array([[[1, -1], [-1, 1]]], dtype='float32')
        ),
    ]
    out_file = make_ribbon(white, pial, newpath=str(tmp_path))
    ribbon = np.asanyarray(nb.load(out_file).dataobj).astype(bool)
    expected = np.array([[[True, True], [True, False]]], dtype=bool)
    assert np.array_equal(ribbon, expected)

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
"""Tests for MSM interface helpers."""

from pathlib import Path

from nipype.utils.filemanip import split_filename

from smriprep.interfaces.msm import MSM


def test_msm_list_outputs_with_explicit_out_base(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    in_mesh = tmp_path / 'lh.sphere.surf.gii'
    in_mesh.write_text('x')
    iface = MSM(in_mesh=str(in_mesh), out_base='L.')
    outputs = iface._list_outputs()
    assert outputs['warped_mesh'].endswith('L.sphere.reg.surf.gii')
    assert outputs['downsampled_warped_mesh'].endswith('L.sphere.LR.reg.surf.gii')
    assert outputs['warped_data'].endswith('L.transformed_and_reprojected.func.gii')


def test_msm_list_outputs_uses_in_mesh_basename(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    in_mesh = tmp_path / 'sub-01_hemi-L_sphere.surf.gii'
    in_mesh.write_text('x')
    iface = MSM(in_mesh=str(in_mesh))
    outputs = iface._list_outputs()
    base = split_filename(str(in_mesh))[1]
    assert Path(outputs['warped_mesh']).name == f'{base}sphere.reg.surf.gii'

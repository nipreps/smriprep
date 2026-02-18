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
"""Tests for FreeSurfer helper behavior."""

import pytest

from smriprep.interfaces.freesurfer import MRIsConvertData, MakeMidthickness, ReconAll


def test_mrisconvertdata_uses_explicit_in_file(tmp_path):
    in_file = tmp_path / 'lh.white'
    in_file.write_text('x')
    iface = MRIsConvertData(in_file=str(in_file), annot_file=str(in_file))
    assert iface._gen_filename('in_file') == str(in_file)


def test_mrisconvertdata_derives_white_surface(tmp_path):
    annot = tmp_path / 'lh.aparc.annot'
    white = tmp_path / 'lh.white'
    annot.write_text('x')
    white.write_text('x')

    iface = MRIsConvertData(annot_file=str(annot))
    assert iface._gen_filename('in_file') == str(white)
    assert iface.inputs.in_file == str(white)


def test_mrisconvertdata_nonhemi_returns_none(tmp_path):
    annot = tmp_path / 'aparc.annot'
    annot.write_text('x')
    iface = MRIsConvertData(annot_file=str(annot))
    assert iface._gen_filename('in_file') is None


def test_mrisconvertdata_requires_one_source():
    iface = MRIsConvertData()
    with pytest.raises(ValueError, match='Missing file'):
        iface._gen_filename('in_file')


def test_make_midthickness_num_threads_update():
    iface = MakeMidthickness()
    iface.inputs.num_threads = 4
    iface._num_threads_update()
    assert iface.inputs.environ['OMP_NUM_THREADS'] == '6'


def test_reconall_format_arg_patch():
    iface = ReconAll()
    hemi_trait = iface.inputs.trait('hemi')
    directive_trait = iface.inputs.trait('directive')
    assert iface._format_arg('hemi', hemi_trait, 'lh') == '-lh-only'
    assert iface._format_arg('directive', directive_trait, 'autorecon1') == '-autorecon1'

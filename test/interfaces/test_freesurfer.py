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
"""Tests for patched FreeSurfer interfaces."""

import nipype.interfaces.freesurfer as fs

from smriprep.interfaces.freesurfer import MRICoreg


def test_mricoreg_no_xor_constraint():
    """The xor between reference_file and subject_id must be removed."""
    coreg = MRICoreg()
    ref_trait = coreg.inputs.trait('reference_file')
    subj_trait = coreg.inputs.trait('subject_id')
    assert not getattr(ref_trait, 'xor', None)
    assert not getattr(subj_trait, 'xor', None)


def test_mricoreg_fields_not_mandatory():
    """Neither reference_file nor subject_id should be mandatory."""
    coreg = MRICoreg()
    assert not coreg.inputs.trait('reference_file').mandatory
    assert not coreg.inputs.trait('subject_id').mandatory


def test_mricoreg_subject_id_requires_subjects_dir():
    """The ``requires`` constraint on subject_id must be preserved."""
    coreg = MRICoreg()
    assert 'subjects_dir' in coreg.inputs.trait('subject_id').requires


def test_mricoreg_accepts_both_reference_and_subject(tmp_path):
    """Setting both reference_file and subject_id must not raise."""
    src = tmp_path / 'bold.nii.gz'
    ref = tmp_path / 'T2.mgz'
    src.touch()
    ref.touch()

    coreg = MRICoreg(
        source_file=str(src),
        reference_file=str(ref),
        subject_id='sub-01',
        subjects_dir=str(tmp_path),
    )
    assert coreg.inputs.reference_file == str(ref)
    assert coreg.inputs.subject_id == 'sub-01'


def test_upstream_mricoreg_xor_exists():
    """Canary: verify the upstream xor constraint still exists.

    If this test starts failing, nipype has fixed the issue and the
    sMRIPrep patch can be removed.
    """
    coreg = fs.MRICoreg()
    ref_trait = coreg.inputs.trait('reference_file')
    subj_trait = coreg.inputs.trait('subject_id')
    assert 'subject_id' in (getattr(ref_trait, 'xor', None) or [])
    assert 'reference_file' in (getattr(subj_trait, 'xor', None) or [])

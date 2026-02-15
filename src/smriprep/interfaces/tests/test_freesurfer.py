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

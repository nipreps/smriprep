import pytest

from ..freesurfer import ValidateSubjectDir


def test_validate_subject_dir(tmp_path):
    validate = ValidateSubjectDir(subjects_dir=tmp_path, subject_id='sub-01')
    with pytest.raises(FileNotFoundError, match='.* does not exist .*'):
        validate.run()

    tmp_path.joinpath('sub-01').mkdir()

    ret = validate.run()
    assert ret.outputs.subjects_dir == str(tmp_path)
    assert ret.outputs.subject_id == 'sub-01'

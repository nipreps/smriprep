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
import pytest

from smriprep.utils.misc import apply_lut, fs_isRunning, stringify_sessions


def _gen_fsdir(tmp_path, isrunning):
    fsdir = tmp_path / 'sample_freesurfer'
    (fsdir / 'sub-01' / 'scripts').mkdir(parents=True)
    (fsdir / 'sub-01' / 'scripts' / 'recon-all.log').write_text('log')
    if isrunning:
        (fsdir / 'sub-01' / 'scripts' / 'IsRunning.rh').write_text('running')
        (fsdir / 'sub-01' / 'scripts' / 'IsRunning.lh').write_text('running')
    return fsdir


@pytest.mark.parametrize(
    ('isrunning', 'mtime_tol', 'error'),
    [
        (False, 86400, None),
        (True, 86400, RuntimeError),
        (True, 0, None),
    ],
)
def test_fs_isRunning(tmp_path, isrunning, mtime_tol, error):
    fs_dir = _gen_fsdir(tmp_path, isrunning)
    if error is None:
        fs_isRunning(fs_dir, 'sub-01', mtime_tol=mtime_tol)
        assert not tuple(fs_dir.glob('**/IsRunning*'))
    else:
        with pytest.raises(error):
            fs_isRunning(fs_dir, 'sub-01', mtime_tol=mtime_tol)
        assert tuple(fs_dir.glob('**/IsRunning*'))


def test_fs_isRunning_warns_on_cleanup(tmp_path):
    import os

    fs_dir = _gen_fsdir(tmp_path, isrunning=True)
    reconlog = fs_dir / 'sub-01' / 'scripts' / 'recon-all.log'
    os.utime(reconlog, (1, 1))

    class _Logger:
        def __init__(self):
            self.msg = None

        def warn(self, msg):
            self.msg = msg

    logger = _Logger()
    fs_isRunning(fs_dir, 'sub-01', mtime_tol=1, logger=logger)
    assert logger.msg is not None
    assert 'Removed "IsRunning*" files' in logger.msg


def test_apply_lut(make_nifti, tmp_path):
    import nibabel as nb
    import numpy as np

    in_dseg = make_nifti(
        tmp_path / 'dseg.nii.gz',
        data=np.array([[[0, 1], [2, 1]]], dtype='int16'),
    )
    out_file = apply_lut(in_dseg, [0, 10, 20], newpath=tmp_path)

    out_img = nb.load(out_file)
    out_data = np.asanyarray(out_img.dataobj)
    assert out_img.get_data_dtype().name == 'int16'
    assert np.array_equal(out_data, np.array([[[0, 10], [20, 10]]], dtype='int16'))


@pytest.mark.parametrize(
    ('sessions', 'kwargs', 'expected'),
    [
        (['a'], {}, 'a'),
        (['a', 'b', 'c'], {'max_length': 12}, 'a-b-c'),
        (['a', 'b', 'toolong'], {}, 'multi-32b3'),
        (['a', 'b', 'toolong'], {'digest_size': 4}, 'multi-f1edd4fd'),
    ],
)
def test_stringify_sessions(sessions, kwargs, expected):
    assert stringify_sessions(sessions, **kwargs) == expected

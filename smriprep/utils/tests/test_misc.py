# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
#
# Copyright 2021 The NiPreps Developers <nipreps@gmail.com>
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

from ..misc import fs_isRunning


def _gen_fsdir(tmp_path, isrunning):
    fsdir = tmp_path / "sample_freesurfer"
    (fsdir / "sub-01" / "scripts").mkdir(parents=True)
    (fsdir / "sub-01" / "scripts" / "recon-all.log").write_text("log")
    if isrunning:
        (fsdir / "sub-01" / "scripts" / "IsRunning.rh").write_text("running")
        (fsdir / "sub-01" / "scripts" / "IsRunning.lh").write_text("running")
    return fsdir


@pytest.mark.parametrize(
    "isrunning,mtime_tol,error",
    [
        (False, 86400, None),
        (True, 86400, RuntimeError),
        (True, 0, None),
    ],
)
def test_fs_isRunning(tmp_path, isrunning, mtime_tol, error):
    fs_dir = _gen_fsdir(tmp_path, isrunning)
    if error is None:
        fs_isRunning(fs_dir, "sub-01", mtime_tol=mtime_tol)
        assert not tuple(fs_dir.glob("**/IsRunning*"))
    else:
        with pytest.raises(error):
            fs_isRunning(fs_dir, "sub-01", mtime_tol=mtime_tol)
        assert tuple(fs_dir.glob("**/IsRunning*"))

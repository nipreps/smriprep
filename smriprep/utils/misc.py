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
"""Self-contained utilities to be used within Function nodes."""


def apply_lut(in_dseg, lut, newpath=None):
    """Map the input discrete segmentation to a new label set (lookup table, LUT)."""
    import numpy as np
    import nibabel as nb
    from nipype.utils.filemanip import fname_presuffix

    if newpath is None:
        from os import getcwd

        newpath = getcwd()

    out_file = fname_presuffix(in_dseg, suffix="_dseg", newpath=newpath)
    lut = np.array(lut, dtype="int16")

    segm = nb.load(in_dseg)
    hdr = segm.header.copy()
    hdr.set_data_dtype("int16")
    segm.__class__(
        lut[np.asanyarray(segm.dataobj, dtype=int)].astype("int16"), segm.affine, hdr
    ).to_filename(out_file)

    return out_file


def fs_isRunning(subjects_dir, subject_id, mtime_tol=86400, logger=None):
    """
    Checks FreeSurfer subjects dir for presence of recon-all blocking ``IsRunning`` files,
    and optionally removes any based on the modification time.

    Parameters
    ----------
    subjects_dir : os.PathLike or None
        Existing FreeSurfer subjects directory
    subject_id : str
        Subject label
    mtime_tol : int
        Tolerance time (in seconds) between current time and last modification of ``recon-all.log``

    Returns
    -------
    subjects_dir : os.PathLike or None

    """
    from pathlib import Path
    import time

    if subjects_dir is None:
        return subjects_dir
    subj_dir = Path(subjects_dir) / subject_id
    if not subj_dir.exists():
        return subjects_dir

    isrunning = tuple(subj_dir.glob("scripts/IsRunning*"))
    if not isrunning:
        return subjects_dir
    reconlog = subj_dir / "scripts" / "recon-all.log"
    # if recon log doesn't exist, just clear IsRunning
    mtime = reconlog.stat().st_mtime if reconlog.exists() else 0
    if (time.time() - mtime) < mtime_tol:
        raise RuntimeError(
            f"""\
The FreeSurfer's subject folder <{subj_dir}> contains IsRunning files that \
may pertain to a current or past execution: {isrunning}.
FreeSurfer cannot run if these are present, to avoid interfering with a running \
process. Please, make sure no other process is running ``recon-all`` on this subject \
and proceed to delete the files listed above."""
        )
    for fl in isrunning:
        fl.unlink()
    if logger:
        logger.warn(f'Removed "IsRunning*" files found under {subj_dir}')
    return subjects_dir

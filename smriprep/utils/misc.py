"""Self-contained utilities to be used within Function nodes."""


def apply_lut(in_dseg, lut, newpath=None):
    """Map the input discrete segmentation to a new label set (lookup table, LUT)."""
    import numpy as np
    import nibabel as nb
    from nipype.utils.filemanip import fname_presuffix

    if newpath is None:
        from os import getcwd
        newpath = getcwd()

    out_file = fname_presuffix(in_dseg, suffix='_dseg', newpath=newpath)
    lut = np.array(lut, dtype='int16')

    segm = nb.load(in_dseg)
    hdr = segm.header.copy()
    hdr.set_data_dtype('int16')
    segm.__class__(lut[np.asanyarray(segm.dataobj, dtype=int)].astype('int16'),
                   segm.affine, hdr).to_filename(out_file)

    return out_file


def fs_isRunning(subjects_dir, subject_id, mtime_tol=86400):
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
    import logging
    from pathlib import Path
    import time

    if subjects_dir is None:
        return subjects_dir
    subj_dir = Path(subjects_dir) / subject_id
    if not subj_dir.exists():
        return subjects_dir

    isrunning = tuple(subj_dir.glob("**/IsRunning*"))
    if not isrunning:
        return subjects_dir
    try:
        reconlog = next(subj_dir.glob("**/recon-all.log"))
    except StopIteration:
        # problems finding recon-all.log, just return subjects_dir
        return subjects_dir

    # if any IsRunning files are found, first check on last modified time of log
    if (time.time() - reconlog.stat().st_mtime) < mtime_tol:
        return subjects_dir

    for fl in isrunning:
        fl.unlink()

    logger = logging.getLogger('nipype.interface')
    logger.warn(f"Removed older IsRunning files found under {subj_dir}")
    return subjects_dir

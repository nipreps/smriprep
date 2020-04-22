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


def check_valid_fs_license():
    """Quickly runs mri_convert to weed out FreeSurfer license issues"""
    import contextlib
    import logging
    import os

    import nibabel as nb
    import numpy as np
    from nipype.interfaces.freesurfer import MRIConvert

    # keep record of interface logging
    iflogger = logging.getLogger('nipype.interface')
    _level = iflogger.level
    iflogger.setLevel(0)  # mute logging

    tmp_file = 'test.nii.gz'
    out_file = 'out.mgz'
    # create test NIfTI
    nb.Nifti1Image(np.zeros((5, 5, 5)), np.eye(4)).to_filename(tmp_file)
    # run simple fs interface
    mric = MRIConvert(in_file=tmp_file, out_file=out_file, out_type='mgz')
    res = mric.run(ignore_exception=True)
    valid = "ERROR: FreeSurfer license file" not in res.runtime.stderr
    # clean up
    with contextlib.suppress(FileNotFoundError):
        os.unlink(tmp_file)
        os.unlink(out_file)

    iflogger.setLevel(_level)  # reset logger
    return valid

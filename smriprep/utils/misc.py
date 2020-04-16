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

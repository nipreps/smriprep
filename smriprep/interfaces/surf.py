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
"""Handling surfaces."""
import os

import numpy as np
import nibabel as nb

from nipype.interfaces.base import (
    BaseInterfaceInputSpec,
    TraitedSpec,
    SimpleInterface,
    File,
    isdefined,
)


class _NormalizeSurfInputSpec(BaseInterfaceInputSpec):
    in_file = File(mandatory=True, exists=True, desc="Freesurfer-generated GIFTI file")
    transform_file = File(exists=True, desc="FSL or LTA affine transform file")


class _NormalizeSurfOutputSpec(TraitedSpec):
    out_file = File(desc="output file with re-centered GIFTI coordinates")


class NormalizeSurf(SimpleInterface):
    """
    Normalize a FreeSurfer-generated GIFTI image.

    FreeSurfer includes volume geometry metadata that serves as an affine
    transformation to apply to coordinates, which is respected by FreeSurfer
    tools, but not other tools, in particular the Connectome Workbench.
    This normalization thus removes the volume geometry, to ensure consistent
    interpretation of the coordinate locations.
    This requires that the GIFTI surface be converted with
    ``mris_convert --to-scanner``, with which FreeSurfer will apply the
    volume geometry. Because FreeSurfer does not update the metadata, there is
    no way to detect programmatically how the file was created, and therefore
    it is the responsibility of the sender to ensure ``mris_convert --to-scanner``
    was used.

    GIFTI files with ``midthickness``/``graymid`` in the name are also updated
    to include the following metadata entries::

        {
            AnatomicalStructureSecondary: MidThickness,
            GeometricType: Anatomical
        }

    This interface is intended to be applied uniformly to GIFTI surface files
    generated from the ``?h.white``/``?h.smoothwm`` and ``?h.pial`` surfaces,
    as well as externally-generated ``?h.midthickness``/``?h.graymid`` files.
    In principle, this should apply safely to any other surface, although it is
    less relevant to surfaces that don't describe an anatomical structure.

    """

    input_spec = _NormalizeSurfInputSpec
    output_spec = _NormalizeSurfOutputSpec

    def _run_interface(self, runtime):
        transform_file = self.inputs.transform_file
        if not isdefined(transform_file):
            transform_file = None
        self._results["out_file"] = normalize_surfs(
            self.inputs.in_file, transform_file, newpath=runtime.cwd
        )
        return runtime


def normalize_surfs(in_file, transform_file, newpath=None):
    """
    Update GIFTI metadata and apply rigid coordinate correction.

    This function removes volume geometry metadata that FreeSurfer includes.
    Connectome Workbench does not respect this metadata, while FreeSurfer will
    apply it when converting with ``mris_convert --to-scanner`` and then again when
    reading with ``freeview``.

    For midthickness surfaces, add MidThickness metadata
    """

    img = nb.load(in_file)
    transform = load_transform(transform_file)
    pointset = img.get_arrays_from_intent("NIFTI_INTENT_POINTSET")[0]

    if not np.allclose(transform, np.eye(4)):
        pointset.data = nb.affines.apply_affine(transform, pointset.data)

    # mris_convert --to-scanner removes VolGeom transform from coordinates,
    # but not metadata.
    # We could set to default LIA affine, but there seems little advantage
    for XYZC in "XYZC":
        for RAS in "RAS":
            pointset.meta.pop(f"VolGeom{XYZC}_{RAS}", None)

    fname = os.path.basename(in_file)
    if "midthickness" in fname.lower() or "graymid" in fname.lower():
        pointset.meta.setdefault("AnatomicalStructureSecondary", "MidThickness")
        pointset.meta.setdefault("GeometricType", "Anatomical")

    if newpath is not None:
        newpath = os.getcwd()
    out_file = os.path.join(newpath, fname)
    img.to_filename(out_file)
    return out_file


def load_transform(fname):
    """Load affine transform from file

    Parameters
    ----------
    fname : str or None
        Filename of an LTA or FSL-style MAT transform file.
        If ``None``, return an identity transform

    Returns
    -------
    affine : (4, 4) numpy.ndarray
    """
    if fname is None:
        return np.eye(4)

    if fname.endswith(".mat"):
        return np.loadtxt(fname)
    elif fname.endswith(".lta"):
        with open(fname, "rb") as fobj:
            for line in fobj:
                if line.startswith(b"1 4 4"):
                    break
            lines = fobj.readlines()[:4]
        return np.genfromtxt(lines)

    raise ValueError("Unknown transform type; pass FSL (.mat) or LTA (.lta)")

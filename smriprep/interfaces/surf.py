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
from pathlib import Path
from typing import Optional

import numpy as np
import nibabel as nb
import nitransforms as nt

from nipype.interfaces.base import (
    BaseInterfaceInputSpec,
    TraitedSpec,
    SimpleInterface,
    File,
    isdefined,
    InputMultiObject,
    traits,
)


class _NormalizeSurfInputSpec(BaseInterfaceInputSpec):
    in_file = File(mandatory=True, exists=True, desc="Freesurfer-generated GIFTI file")
    transform_file = File(exists=True, desc="FSL, LTA or ITK affine transform file")


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


class FixGiftiMetadataInputSpec(TraitedSpec):
    in_file = File(mandatory=True, exists=True, desc="Freesurfer-generated GIFTI file")


class FixGiftiMetadataOutputSpec(TraitedSpec):
    out_file = File(desc="output file with fixed metadata")


class FixGiftiMetadata(SimpleInterface):
    """Fix known incompatible metadata in GIFTI files.

    Currently resolves:

    * FreeSurfer setting GeometryType to Sphere instead of Spherical
    """

    input_spec = FixGiftiMetadataInputSpec
    output_spec = FixGiftiMetadataOutputSpec

    def _run_interface(self, runtime):
        self._results["out_file"] = fix_gifti_metadata(self.inputs.in_file, newpath=runtime.cwd)
        return runtime


class AggregateSurfacesInputSpec(TraitedSpec):
    surfaces = InputMultiObject(File(exists=True), desc="Input surfaces")
    morphometrics = InputMultiObject(File(exists=True), desc="Input morphometrics")


class AggregateSurfacesOutputSpec(TraitedSpec):
    pial = traits.List(File(), maxlen=2, desc="Pial surfaces")
    white = traits.List(File(), maxlen=2, desc="White surfaces")
    inflated = traits.List(File(), maxlen=2, desc="Inflated surfaces")
    midthickness = traits.List(File(), maxlen=2, desc="Midthickness (or graymid) surfaces")
    thickness = traits.List(File(), maxlen=2, desc="Cortical thickness maps")
    sulc = traits.List(File(), maxlen=2, desc="Sulcal depth maps")
    curv = traits.List(File(), maxlen=2, desc="Curvature maps")


class AggregateSurfaces(SimpleInterface):
    """Aggregate and group surfaces & morphometrics into left/right pairs."""
    input_spec = AggregateSurfacesInputSpec
    output_spec = AggregateSurfacesOutputSpec

    def _run_interface(self, runtime):
        from collections import defaultdict
        import os
        import re

        container = defaultdict(list)
        inputs = (self.inputs.surfaces or []) + (self.inputs.morphometrics or [])
        findre = re.compile(
            r'(?:^|[^d])(?P<name>white|pial|inflated|midthickness|thickness|sulc|curv)'
        )
        for surface in sorted(inputs, key=os.path.basename):
            match = findre.search(os.path.basename(surface))
            if match:
                container[match.group('name')].append(surface)
        for name, files in container.items():
            self._results[name] = files
        return runtime


class MakeRibbonInputSpec(TraitedSpec):
    white_distvols = traits.List(
        File(exists=True), minlen=2, maxlen=2, desc="White matter distance volumes"
    )
    pial_distvols = traits.List(
        File(exists=True), minlen=2, maxlen=2, desc="Pial matter distance volumes"
    )


class MakeRibbonOutputSpec(TraitedSpec):
    ribbon = File(desc="Binary ribbon mask")


class MakeRibbon(SimpleInterface):
    """Create a binary ribbon mask from white and pial distance volumes."""

    input_spec = MakeRibbonInputSpec
    output_spec = MakeRibbonOutputSpec

    def _run_interface(self, runtime):
        self._results["ribbon"] = make_ribbon(
            self.inputs.white_distvols, self.inputs.pial_distvols, newpath=runtime.cwd
        )
        return runtime


def normalize_surfs(
    in_file: str, transform_file: str | None, newpath: Optional[str] = None
) -> str:
    """
    Update GIFTI metadata and apply rigid coordinate correction.

    This function removes volume geometry metadata that FreeSurfer includes.
    Connectome Workbench does not respect this metadata, while FreeSurfer will
    apply it when converting with ``mris_convert --to-scanner`` and then again when
    reading with ``freeview``.

    For midthickness surfaces, add MidThickness metadata
    """

    img = nb.load(in_file)
    if transform_file is None:
        transform = np.eye(4)
    else:
        xfm_fmt = {
            ".txt": "itk",
            ".mat": "fsl",
            ".lta": "fs",
        }[Path(transform_file).suffix]
        transform = nt.linear.load(transform_file, fmt=xfm_fmt).matrix
    pointset = img.get_arrays_from_intent("NIFTI_INTENT_POINTSET")[0]

    if not np.allclose(transform, np.eye(4)):
        pointset.data = nb.affines.apply_affine(transform, pointset.data)

    fname = os.path.basename(in_file)
    if "graymid" in fname.lower():
        # Rename graymid to midthickness
        fname = fname.replace("graymid", "midthickness")
    if "midthickness" in fname.lower():
        pointset.meta.setdefault("AnatomicalStructureSecondary", "MidThickness")
        pointset.meta.setdefault("GeometricType", "Anatomical")

    # FreeSurfer incorrectly uses "Sphere" for spherical surfaces
    if pointset.meta.get("GeometricType") == "Sphere":
        pointset.meta["GeometricType"] = "Spherical"
    else:
        # mris_convert --to-scanner removes VolGeom transform from coordinates,
        # but not metadata.
        # We could set to default LIA affine, but there seems little advantage.
        #
        # Following the lead of HCP pipelines, we only adjust the coordinates
        # for anatomical surfaces. To ensure consistent treatment by FreeSurfer,
        # we leave the metadata for spherical surfaces intact.
        for XYZC in "XYZC":
            for RAS in "RAS":
                pointset.meta.pop(f"VolGeom{XYZC}_{RAS}", None)

    if newpath is not None:
        newpath = os.getcwd()
    out_file = os.path.join(newpath, fname)
    img.to_filename(out_file)
    return out_file


def fix_gifti_metadata(in_file: str, newpath: Optional[str] = None) -> str:
    """Fix known incompatible metadata in GIFTI files.

    Currently resolves:

    * FreeSurfer setting GeometryType to Sphere instead of Spherical
    """

    img = nb.GiftiImage.from_filename(in_file)
    pointset = img.get_arrays_from_intent("NIFTI_INTENT_POINTSET")[0]

    # FreeSurfer incorrectly uses "Sphere" for spherical surfaces
    # This is not fixed as of FreeSurfer 7.4.0
    # https://github.com/freesurfer/freesurfer/pull/1112
    if pointset.meta.get("GeometricType") == "Sphere":
        pointset.meta["GeometricType"] = "Spherical"

    if newpath is not None:
        newpath = os.getcwd()
    out_file = os.path.join(newpath, os.path.basename(in_file))
    img.to_filename(out_file)
    return out_file


def make_ribbon(
    white_distvols: list[str],
    pial_distvols: list[str],
    newpath: Optional[str] = None,
) -> str:
    base_img = nb.load(white_distvols[0])
    header = base_img.header
    header.set_data_dtype("uint8")

    ribbons = [
        (np.array(nb.load(white).dataobj) > 0) & (np.array(nb.load(pial).dataobj) < 0)
        for white, pial in zip(white_distvols, pial_distvols)
    ]

    if newpath is not None:
        newpath = os.getcwd()
    out_file = os.path.join(newpath, "ribbon.nii.gz")

    ribbon = base_img.__class__(ribbons[0] | ribbons[1], base_img.affine, base_img.header)
    ribbon.to_filename(out_file)
    return out_file

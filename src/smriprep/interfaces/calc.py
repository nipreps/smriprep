# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
#
# Copyright 2024 The NiPreps Developers <nipreps@gmail.com>
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
"""Image calculation interfaces."""

import os
from pathlib import Path

import nibabel as nb
import numpy as np
from nipype.interfaces.base import (
    File,
    SimpleInterface,
    TraitedSpec,
)


class T1T2RatioInputSpec(TraitedSpec):
    t1w_file = File(exists=True, mandatory=True, desc='T1-weighted image')
    t2w_file = File(exists=True, mandatory=True, desc='T2-weighted image')
    mask_file = File(exists=True, desc='Brain mask')


class T1T2RatioOutputSpec(TraitedSpec):
    t1t2_file = File(exists=True, desc='T1/T2 ratio image')


class T1T2Ratio(SimpleInterface):
    input_spec = T1T2RatioInputSpec
    output_spec = T1T2RatioOutputSpec

    def _run_interface(self, runtime):
        self._results['t1t2_file'] = make_t1t2_ratio(
            self.inputs.t1w_file, self.inputs.t2w_file, self.inputs.mask_file, newpath=runtime.cwd
        )
        return runtime


def make_t1t2_ratio(
    t1w_file: str,
    t2w_file: str,
    mask_file: str | None = None,
    newpath: str | None = None,
) -> str:
    t1w = nb.load(t1w_file)
    t2w = nb.load(t2w_file)
    if mask_file is not None:
        mask = np.asanyarray(nb.load(mask_file).dataobj) != 0
    else:
        mask = np.ones(t1w.shape, dtype=bool)

    t1w_data = t1w.get_fdata(dtype=np.float32)
    t2w_data = t2w.get_fdata(dtype=np.float32)

    t1t2_data = np.zeros_like(t1w_data)

    ratio = t1w_data[mask] / t2w_data[mask]
    ratio[~np.isfinite(ratio)] = 0
    minval = ratio.min()
    maxval = ratio.max()

    t1t2_data[mask] = (ratio - minval) / (maxval - minval) * 100

    t1t2 = nb.Nifti1Image(t1t2_data, t1w.affine, t1w.header)
    t1t2.header.set_data_dtype(np.float32)

    t1t2_path = Path(newpath or os.getcwd()) / 't1t2_ratio.nii.gz'

    t1t2.to_filename(t1t2_path)

    return str(t1t2_path)

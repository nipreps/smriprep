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
from nipype.interfaces.base import traits
from nipype.interfaces.fsl.preprocess import FAST as _FAST
from nipype.interfaces.fsl.preprocess import FASTInputSpec


class _FixTraitFASTInputSpec(FASTInputSpec):
    bias_iters = traits.Range(
        low=0,
        high=10,
        argstr='-I %d',
        desc='number of main-loop iterations during bias-field removal',
    )


class FAST(_FAST):
    """
    A replacement for nipype.interfaces.fsl.preprocess.FAST that allows
    `bias_iters=0` to disable bias field correction entirely

    >>> from smriprep.interfaces.fsl import FAST
    >>> fast = FAST()
    >>> fast.inputs.in_files = 'sub-01_desc-warped_T1w.nii.gz'
    >>> fast.inputs.bias_iters = 0
    >>> fast.cmdline
    'fast -I 0 -S 1 sub-01_desc-warped_T1w.nii.gz'
    """

    input_spec = _FixTraitFASTInputSpec

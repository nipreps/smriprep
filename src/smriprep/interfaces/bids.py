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
"""BIDS-related interfaces."""

from pathlib import Path

from bids.utils import listify
from nipype.interfaces.base import (
    DynamicTraitedSpec,
    SimpleInterface,
    TraitedSpec,
    isdefined,
    traits,
)
from nipype.interfaces.io import add_traits
from nipype.interfaces.utility.base import _ravel

from ..utils.bids import _find_nearest_path


class _BIDSURIInputSpec(DynamicTraitedSpec):
    dataset_links = traits.Dict(mandatory=True, desc='Dataset links')
    out_dir = traits.Str(mandatory=True, desc='Output directory')


class _BIDSURIOutputSpec(TraitedSpec):
    out = traits.List(
        traits.Str,
        desc='BIDS URI(s) for file',
    )


class BIDSURI(SimpleInterface):
    """Convert input filenames to BIDS URIs, based on links in the dataset.

    This interface can combine multiple lists of inputs.
    """

    input_spec = _BIDSURIInputSpec
    output_spec = _BIDSURIOutputSpec

    def __init__(self, numinputs=0, **inputs):
        super().__init__(**inputs)
        self._numinputs = numinputs
        if numinputs >= 1:
            input_names = [f'in{i + 1}' for i in range(numinputs)]
        else:
            input_names = []
        add_traits(self.inputs, input_names)

    def _run_interface(self, runtime):
        inputs = [getattr(self.inputs, f'in{i + 1}') for i in range(self._numinputs)]
        in_files = listify(inputs)
        in_files = _ravel(in_files)
        # Remove undefined inputs
        in_files = [f for f in in_files if isdefined(f)]
        # Convert the dataset links to BIDS URI prefixes
        updated_keys = {f'bids:{k}:': Path(v) for k, v in self.inputs.dataset_links.items()}
        updated_keys['bids::'] = Path(self.inputs.out_dir)
        # Convert the paths to BIDS URIs
        out = [_find_nearest_path(updated_keys, f) for f in in_files]
        self._results['out'] = out

        return runtime

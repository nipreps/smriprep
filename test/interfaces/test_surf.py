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
import nibabel as nb
import numpy as np
from nipype.pipeline import engine as pe

from smriprep.interfaces.surf import MakeRibbon
from test.interfaces.data import load as load_test_data


def test_MakeRibbon(tmp_path):
    res_template = 'sub-fsaverage_res-4_hemi-{hemi}_desc-cropped_{surf}dist.nii.gz'
    white, pial = (
        [load_test_data(res_template.format(hemi=hemi, surf=surf)) for hemi in 'LR']
        for surf in ('wm', 'pial')
    )

    make_ribbon = pe.Node(
        MakeRibbon(white_distvols=white, pial_distvols=pial),
        name='make_ribbon',
        base_dir=tmp_path,
    )

    result = make_ribbon.run()

    ribbon = nb.load(result.outputs.ribbon)
    expected = nb.load(load_test_data('sub-fsaverage_res-4_desc-cropped_ribbon.nii.gz'))

    assert ribbon.shape == expected.shape
    assert np.allclose(ribbon.affine, expected.affine)
    assert np.array_equal(ribbon.dataobj, expected.dataobj)

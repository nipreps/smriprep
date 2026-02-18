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
"""Tests for GIFTI interfaces."""

import nibabel as nb
import numpy as np
import pytest

from smriprep.interfaces.gifti import MetricMath


@pytest.mark.parametrize(
    ('operation', 'expected'),
    [
        ('invert', np.array([-1.0, 2.0, -3.0], dtype='float32')),
        ('abs', np.array([1.0, 2.0, 3.0], dtype='float32')),
        ('bin', np.array([1, 0, 1], dtype='uint8')),
    ],
)
def test_metricmath_operations(make_gifti_metric, tmp_path, operation, expected):
    in_file = make_gifti_metric(tmp_path / 'metric.shape.gii', data=np.array([1.0, -2.0, 3.0]))
    interface = MetricMath(
        metric_file=in_file,
        operation=operation,
        hemisphere='L',
        subject_id='sub-01',
        metric='sulc',
    )
    result = interface.run(cwd=tmp_path)
    out_img = nb.load(result.outputs.metric_file)
    darray = out_img.darrays[0]
    assert np.array_equal(darray.data, expected)
    assert out_img.meta['AnatomicalStructurePrimary'] == 'CortexLeft'
    assert darray.meta['Name'] == 'sub-01_L_sulc'
    if operation == 'bin':
        assert darray.data.dtype == np.uint8


def test_metricmath_uses_default_subject(make_gifti_metric, tmp_path):
    in_file = make_gifti_metric(tmp_path / 'metric.shape.gii')
    result = MetricMath(
        metric_file=in_file,
        operation='invert',
        hemisphere='R',
        metric='thickness',
    ).run(cwd=tmp_path)
    out_img = nb.load(result.outputs.metric_file)
    assert out_img.darrays[0].meta['Name'].startswith('sub-XYZ_R_thickness')

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
"""Tests for CIFTI helpers."""

import nibabel as nb
import numpy as np
import pytest

from smriprep.interfaces.cifti import _create_cifti_image, _prepare_cifti


@pytest.mark.parametrize(
    ('grayordinates', 'density', 'grayords'),
    [
        ('91k', '32k', '91,282'),
        ('170k', '59k', '170,494'),
    ],
)
def test_prepare_cifti(grayordinates, density, grayords, monkeypatch):
    monkeypatch.setattr(
        'smriprep.interfaces.cifti.tf.get',
        lambda template, **kwargs: f"/tpl-{template}_hemi-{kwargs['hemi']}_den-{kwargs['density']}.label.gii",
    )
    surface_labels, metadata = _prepare_cifti(grayordinates)
    assert len(surface_labels) == 2
    assert all(f'den-{density}' in label for label in surface_labels)
    assert grayords in metadata['Density']
    assert 'CIFTI_STRUCTURE_CORTEX_LEFT' in metadata['SpatialReference']


def test_prepare_cifti_unsupported():
    with pytest.raises(NotImplementedError):
        _prepare_cifti('42k')


def test_create_cifti_image(make_gifti_label, make_gifti_metric, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    labels = (
        make_gifti_label(tmp_path / 'L.label.gii', data=np.array([1, 0, 1], dtype='int32')),
        make_gifti_label(tmp_path / 'R.label.gii', data=np.array([0, 1, 1], dtype='int32')),
    )
    scalars = (
        make_gifti_metric(tmp_path / 'sub-01_hemi-L_curv.shape.gii', data=np.array([1.0, 2.0, 3.0])),
        make_gifti_metric(tmp_path / 'sub-01_hemi-R_curv.shape.gii', data=np.array([4.0, 5.0, 6.0])),
    )

    out_file = _create_cifti_image(
        scalar_surfs=scalars,
        surface_labels=labels,
        scalar_name='curv',
        metadata={'foo': 'bar'},
    )

    img = nb.load(out_file)
    data = np.asanyarray(img.dataobj)
    assert data.shape == (1, 4)
    assert np.array_equal(data[0], np.array([1.0, 3.0, 5.0, 6.0], dtype='float32'))
    assert img.header.get_axis(0).name[0] == 'curv'

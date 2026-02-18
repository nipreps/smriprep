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
"""Shared fixtures for unit tests."""

import os
from pathlib import Path

import nibabel as nb
import numpy as np
import pytest


@pytest.fixture(scope='session', autouse=True)
def _set_mplconfigdir(tmp_path_factory):
    """Avoid matplotlib cache warnings in CI and sandboxed environments."""
    previous = {
        'MPLCONFIGDIR': os.environ.get('MPLCONFIGDIR'),
        'XDG_CACHE_HOME': os.environ.get('XDG_CACHE_HOME'),
    }
    mplconfigdir = str(tmp_path_factory.mktemp('mplconfig'))
    os.environ['MPLCONFIGDIR'] = mplconfigdir
    os.environ['XDG_CACHE_HOME'] = str(tmp_path_factory.mktemp('xdg-cache'))
    yield
    for key, value in previous.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


@pytest.fixture
def make_nifti(tmp_path):
    """Create tiny NIfTI files for fast unit tests."""

    def _make(path, data=None, affine=None):
        path = Path(path)
        if data is None:
            data = np.zeros((3, 3, 3), dtype='float32')
        if affine is None:
            affine = np.eye(4)
        img = nb.Nifti1Image(np.asarray(data), affine)
        img.to_filename(path)
        return str(path)

    return _make


@pytest.fixture
def make_gifti_metric():
    """Create a single-darray GIFTI metric file."""

    def _make(path, data=None, intent='NIFTI_INTENT_SHAPE'):
        path = Path(path)
        if data is None:
            data = np.array([0.0, 1.0, 2.0], dtype='float32')
        darray = nb.gifti.GiftiDataArray(np.asarray(data, dtype='float32'), intent=intent)
        nb.GiftiImage(darrays=[darray]).to_filename(path)
        return str(path)

    return _make


@pytest.fixture
def make_gifti_label():
    """Create a single-darray GIFTI label file."""

    def _make(path, data=None):
        path = Path(path)
        if data is None:
            data = np.array([1, 0, 1, 1], dtype='int32')
        darray = nb.gifti.GiftiDataArray(
            np.asarray(data, dtype='int32'), intent='NIFTI_INTENT_LABEL'
        )
        nb.GiftiImage(darrays=[darray]).to_filename(path)
        return str(path)

    return _make


@pytest.fixture
def make_gifti_surface():
    """Create a minimal GIFTI surface with pointset and triangle arrays."""

    def _make(path, meta=None):
        path = Path(path)
        coords = np.array(
            [
                [0.0, 0.0, 0.0],
                [1.0, 0.0, 0.0],
                [0.0, 1.0, 0.0],
            ],
            dtype='float32',
        )
        faces = np.array([[0, 1, 2]], dtype='int32')
        pointset = nb.gifti.GiftiDataArray(coords, intent='NIFTI_INTENT_POINTSET')
        triangles = nb.gifti.GiftiDataArray(faces, intent='NIFTI_INTENT_TRIANGLE')
        if meta:
            for key, value in meta.items():
                pointset.meta[key] = value
        nb.GiftiImage(darrays=[pointset, triangles]).to_filename(path)
        return str(path)

    return _make

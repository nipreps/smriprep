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
"""Tests for base workflow helpers."""

from smriprep.workflows.base import _prefix


def test_prefix_subject_only():
    assert _prefix('01') == 'sub-01'
    assert _prefix('sub-01') == 'sub-01'


def test_prefix_with_session():
    assert _prefix('01', 'pre') == 'sub-01_ses-pre'
    assert _prefix('01', 'ses-pre') == 'sub-01_ses-pre'
    assert _prefix('01', ['pre', 'post']) == 'sub-01_ses-pre-post'

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
"""Tests for registration workflow helper functions."""

from nipype.interfaces.base import Undefined
from nipype.pipeline import engine as pe

from smriprep.workflows.fit.registration import _fmt_cohort, _make_outputnode, _set_reference


def test_make_outputnode_with_and_without_join():
    workflow = pe.Workflow(name='wf_join')
    pout = _make_outputnode(workflow, ['template', 'xfm'], joinsource='inputnode')
    names = {node.name for node in workflow._get_all_nodes()}
    assert pout.name == 'poutputnode'
    assert {'poutputnode', 'outputnode'} <= names

    workflow_nojoin = pe.Workflow(name='wf_nojoin')
    out = _make_outputnode(workflow_nojoin, ['template'], joinsource=None)
    assert out.name == 'outputnode'
    assert {node.name for node in workflow_nojoin._get_all_nodes()} == set()


def test_fmt_cohort():
    template, spec = _fmt_cohort('MNIPediatricAsym', {'cohort': '3', 'resolution': 1})
    assert template == 'MNIPediatricAsym:cohort-3'
    assert spec == {'resolution': 1}


def test_set_reference():
    assert _set_reference('T1w', '/mock/tpl-T1w.nii.gz') == ('T1w', Undefined)
    assert _set_reference('T2w', '/mock/tpl-T1w.nii.gz', '/mock/tpl-T2w.nii.gz') == (
        'T2w',
        Undefined,
    )
    assert _set_reference('T2w', '/mock/tpl-T1w.nii.gz', None) == ('T1w', False)

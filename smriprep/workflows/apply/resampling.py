# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
#
# Copyright 2022 The NiPreps Developers <nipreps@gmail.com>
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

"""Spatial resampling workflows"""
from nipype.pipeline import engine as pe
from nipype.interfaces import utility as niu

from niworkflows.engine.workflows import LiterateWorkflow as Workflow
from niworkflows.interfaces.fixes import FixHeaderApplyTransforms as ApplyTransforms
from ...interfaces.templateflow import TemplateFlowSelect


def init_resample_template_wf(
    *,
    joinsource=None,
    name="resample_template_wf",
    **apply_transforms_kwargs,
):
    """
    Build an individual spatial normalization workflow using ``antsRegistration``.

    Workflow Graph
        .. workflow ::
            :graph2use: orig
            :simple_form: yes

            from smriprep.workflows.apply.resampling import init_resample_template_wf
            wf = init_resample_template_wf(
                interpolation='LanczosWindowedSinc',
                default_value=0,
                float=True,
            )

    .. important::
        If ``joinsource`` is defined, then there will be an *unjoined* node
        ``poutputnode`` (*parameteric output node*).
        ``outputnode`` will be a ``JoinNode`` in this case and all fields will be
        lists; otherwise it is a standard output node.

    Parameters
    ----------
    name: str
        The name of the workflow, must be unique within a workflow level
    joinsource: str, optional
        If defined, the name of the node where the iterable that parameterizes
        this workflow was defined.
    **apply_transforms_kwargs: dict
        Valid parameters to ants.ApplyTransforms

    Inputs
    ------
    anat2std_xfm
        The T1w-to-template transform.
    moving_image
        The input image(s) that will be normalized to standard space.
    template
        Template name
    template_spec
        Template specification

    Outputs
    -------
    out_file
        The moving image after spatial normalization, in template space.

    """
    workflow = Workflow(name=name)

    inputnode = pe.Node(
        niu.IdentityInterface(
            fields=[
                "anat2std_xfm",
                "moving_image",
                "template",
                "template_spec",
            ]
        ),
        name="inputnode",
    )

    outputnode = _make_outputnode(workflow, ["out_file"], joinsource)

    tf_select = pe.Node(
        TemplateFlowSelect(resolution=1),
        name="tf_select",
        run_without_submitting=True,
    )

    listify = pe.Node(niu.Function(function=_ensure_list), name='listify')

    apply = pe.MapNode(
        ApplyTransforms(**apply_transforms_kwargs),
        iterfield=["input_image"],
        name="apply",
    )

    # fmt:off
    workflow.connect([
        (inputnode, tf_select, [
            ('template', 'template'),
            ('template_spec', 'template_spec'),
        ]),
        (inputnode, listify, [('moving_image', 'fname')]),
        (inputnode, apply, [('anat2std_xfm', 'transforms')]),
        (listify, apply, [('out', 'input_image')]),
        (apply, outputnode, [('output_image', 'out_file')]),
    ])
    # fmt:on

    return workflow


def _make_outputnode(workflow, out_fields, joinsource):
    if joinsource:
        pout = pe.Node(niu.IdentityInterface(fields=out_fields), name="poutputnode")
        out = pe.Node(
            niu.IdentityInterface(fields=out_fields),
            name="outputnode",
            joinsource=joinsource
        )
        workflow.connect([(pout, out, [(f, f) for f in out_fields])])
        return pout
    return pe.Node(niu.IdentityInterface(fields=out_fields), name="outputnode")


def _ensure_list(fname):
    if isinstance(fname, str):
        return [fname]
    elif isinstance(fname, list):
        return fname
    else:
        return list(fname)

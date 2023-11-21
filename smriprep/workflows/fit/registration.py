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
"""Spatial normalization workflows."""
from collections import defaultdict

from nipype.interfaces import ants
from nipype.interfaces import utility as niu
from nipype.interfaces.ants.base import Info as ANTsInfo
from nipype.pipeline import engine as pe
from niworkflows.engine.workflows import LiterateWorkflow as Workflow
from niworkflows.interfaces.norm import SpatialNormalization
from templateflow import __version__ as tf_ver
from templateflow.api import get_metadata

from ...interfaces.templateflow import TemplateDesc, TemplateFlowSelect


def init_register_template_wf(
    *,
    sloppy,
    omp_nthreads,
    templates,
    name='register_template_wf',
):
    """
    Build an individual spatial normalization workflow using ``antsRegistration``.

    Workflow Graph
        .. workflow ::
            :graph2use: orig
            :simple_form: yes

            from smriprep.workflows.fit.registration import init_register_template_wf
            wf = init_register_template_wf(
                sloppy=False,
                omp_nthreads=1,
                templates=['MNI152NLin2009cAsym', 'MNI152NLin6Asym'],
            )

    .. important::
        This workflow defines an iterable input over the input parameter ``templates``,
        so Nipype will produce one copy of the downstream workflows which connect
        ``poutputnode.template`` or ``poutputnode.template_spec`` to their inputs
        (``poutputnode`` stands for *parametric output node*).
        Nipype refers to this expansion of the graph as *parameterized execution*.
        If a joint list of values is required (and thus cutting off parameterization),
        please use the equivalent outputs of ``outputnode`` (which *joins* all the
        parameterized execution paths).

    Parameters
    ----------
    sloppy : :obj:`bool`
        Apply sloppy arguments to speed up processing. Use with caution,
        registration processes will be very inaccurate.
    omp_nthreads : :obj:`int`
        Maximum number of threads an individual process may use.
    templates : :obj:`list` of :obj:`str`
        List of standard space fullnames (e.g., ``MNI152NLin6Asym``
        or ``MNIPediatricAsym:cohort-4``) which are targets for spatial
        normalization.

    Inputs
    ------
    moving_image
        The input image that will be normalized to standard space.
    lesion_mask
        (optional) A mask to exclude regions from the cost-function
        input domain to enable standardization of lesioned brains.
    template
        Template name and specification

    Outputs
    -------
    anat2std_xfm
        The T1w-to-template transform.
    std2anat_xfm
        The template-to-T1w transform.
    template
        Template name extracted from the input parameter ``template``, for further
        use in downstream nodes.
    template_spec
        Template specifications extracted from the input parameter ``template``, for
        further use in downstream nodes.

    """
    ntpls = len(templates)
    workflow = Workflow(name=name)

    if templates:
        workflow.__desc__ = """\
Volume-based spatial normalization to {targets} ({targets_id}) was performed through
nonlinear registration with `antsRegistration` (ANTs {ants_ver}),
using brain-extracted versions of both T1w reference and the T1w template.
The following template{tpls} were selected for spatial normalization
and accessed with *TemplateFlow* [{tf_ver}, @templateflow]:
""".format(
            ants_ver=ANTsInfo.version() or '(version unknown)',
            targets='%s standard space%s'
            % (
                defaultdict('several'.format, {1: 'one', 2: 'two', 3: 'three', 4: 'four'})[ntpls],
                's' * (ntpls != 1),
            ),
            targets_id=', '.join(templates),
            tf_ver=tf_ver,
            tpls=(' was', 's were')[ntpls != 1],
        )

        # Append template citations to description
        for template in templates:
            template_meta = get_metadata(template.split(':')[0])
            template_refs = ['@%s' % template.split(':')[0].lower()]

            if template_meta.get('RRID', None):
                template_refs += ['RRID:%s' % template_meta['RRID']]

            workflow.__desc__ += """\
*{template_name}* [{template_refs}; TemplateFlow ID: {template}]""".format(
                template=template,
                template_name=template_meta['Name'],
                template_refs=', '.join(template_refs),
            )
            workflow.__desc__ += '.\n' if template == templates[-1] else ', '

    inputnode = pe.Node(
        niu.IdentityInterface(
            fields=[
                'lesion_mask',
                'moving_image',
                'moving_mask',
                'template',
            ]
        ),
        name='inputnode',
    )
    inputnode.iterables = [('template', templates)]

    out_fields = [
        'anat2std_xfm',
        'std2anat_xfm',
        'template',
        'template_spec',
    ]
    outputnode = _make_outputnode(workflow, out_fields, joinsource='inputnode')

    split_desc = pe.Node(TemplateDesc(), run_without_submitting=True, name='split_desc')

    tf_select = pe.Node(
        TemplateFlowSelect(resolution=1 + sloppy),
        name='tf_select',
        run_without_submitting=True,
    )

    # With the improvements from nipreps/niworkflows#342 this truncation is now necessary
    trunc_mov = pe.Node(
        ants.ImageMath(operation='TruncateImageIntensity', op2='0.01 0.999 256'),
        name='trunc_mov',
    )

    registration = pe.Node(
        SpatialNormalization(
            float=True,
            flavor=['precise', 'testing'][sloppy],
        ),
        name='registration',
        n_procs=omp_nthreads,
        mem_gb=2,
    )

    # fmt:off
    workflow.connect([
        (inputnode, split_desc, [('template', 'template')]),
        (inputnode, trunc_mov, [('moving_image', 'op1')]),
        (inputnode, registration, [
            ('moving_mask', 'moving_mask'),
            ('lesion_mask', 'lesion_mask')]),
        (split_desc, tf_select, [
            ('name', 'template'),
            ('spec', 'template_spec'),
        ]),
        (split_desc, registration, [
            ('name', 'template'),
            ('spec', 'template_spec'),
        ]),
        (trunc_mov, registration, [
            ('output_image', 'moving_image')]),
        (split_desc, outputnode, [
            ('name', 'template'),
            ('spec', 'template_spec'),
        ]),
        (registration, outputnode, [
            ('composite_transform', 'anat2std_xfm'),
            ('inverse_composite_transform', 'std2anat_xfm'),
        ]),
    ])
    # fmt:on

    return workflow


def _make_outputnode(workflow, out_fields, joinsource):
    if joinsource:
        pout = pe.Node(niu.IdentityInterface(fields=out_fields), name='poutputnode')
        out = pe.JoinNode(
            niu.IdentityInterface(fields=out_fields), name='outputnode', joinsource=joinsource
        )
        workflow.connect([(pout, out, [(f, f) for f in out_fields])])
        return pout
    return pe.Node(niu.IdentityInterface(fields=out_fields), name='outputnode')

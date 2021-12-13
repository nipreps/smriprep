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
from nipype.pipeline import engine as pe
from nipype.interfaces import utility as niu

from nipype.interfaces import ants
from nipype.interfaces.ants.base import Info as ANTsInfo

from templateflow.api import get_metadata
from niworkflows.engine.workflows import LiterateWorkflow as Workflow
from niworkflows.interfaces.norm import SpatialNormalization
from niworkflows.interfaces.fixes import FixHeaderApplyTransforms as ApplyTransforms
from ..interfaces.templateflow import TemplateFlowSelect, TemplateDesc


def init_anat_norm_wf(
    *,
    debug,
    omp_nthreads,
    templates,
    name="anat_norm_wf",
):
    """
    Build an individual spatial normalization workflow using ``antsRegistration``.

    Workflow Graph
        .. workflow ::
            :graph2use: orig
            :simple_form: yes

            from smriprep.workflows.norm import init_anat_norm_wf
            wf = init_anat_norm_wf(
                debug=False,
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
    debug : :obj:`bool`
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
    moving_mask
        A precise brain mask separating skull/skin/fat from brain
        structures.
    moving_segmentation
        A brain tissue segmentation of the ``moving_image``.
    moving_tpms
        tissue probability maps (TPMs) corresponding to the
        ``moving_segmentation``.
    lesion_mask
        (optional) A mask to exclude regions from the cost-function
        input domain to enable standardization of lesioned brains.
    orig_t1w
        The original T1w image from the BIDS structure.
    template
        Template name and specification

    Outputs
    -------
    standardized
        The T1w after spatial normalization, in template space.
    anat2std_xfm
        The T1w-to-template transform.
    std2anat_xfm
        The template-to-T1w transform.
    std_mask
        The ``moving_mask`` in template space (matches ``standardized`` output).
    std_dseg
        The ``moving_segmentation`` in template space (matches ``standardized``
        output).
    std_tpms
        The ``moving_tpms`` in template space (matches ``standardized`` output).
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
The following template{tpls} selected for spatial normalization:
""".format(
            ants_ver=ANTsInfo.version() or "(version unknown)",
            targets="%s standard space%s"
            % (
                defaultdict(
                    "several".format, {1: "one", 2: "two", 3: "three", 4: "four"}
                )[ntpls],
                "s" * (ntpls != 1),
            ),
            targets_id=", ".join(templates),
            tpls=(" was", "s were")[ntpls != 1],
        )

        # Append template citations to description
        for template in templates:
            template_meta = get_metadata(template.split(":")[0])
            template_refs = ["@%s" % template.split(":")[0].lower()]

            if template_meta.get("RRID", None):
                template_refs += ["RRID:%s" % template_meta["RRID"]]

            workflow.__desc__ += """\
*{template_name}* [{template_refs}; TemplateFlow ID: {template}]""".format(
                template=template,
                template_name=template_meta["Name"],
                template_refs=", ".join(template_refs),
            )
            workflow.__desc__ += ".\n" if template == templates[-1] else ", "

    inputnode = pe.Node(
        niu.IdentityInterface(
            fields=[
                "lesion_mask",
                "moving_image",
                "moving_mask",
                "moving_segmentation",
                "moving_tpms",
                "orig_t1w",
                "template",
            ]
        ),
        name="inputnode",
    )
    inputnode.iterables = [("template", templates)]

    out_fields = [
        "anat2std_xfm",
        "standardized",
        "std2anat_xfm",
        "std_dseg",
        "std_mask",
        "std_tpms",
        "template",
        "template_spec",
    ]
    poutputnode = pe.Node(niu.IdentityInterface(fields=out_fields), name="poutputnode")

    split_desc = pe.Node(TemplateDesc(), run_without_submitting=True, name="split_desc")

    tf_select = pe.Node(
        TemplateFlowSelect(resolution=1 + debug),
        name="tf_select",
        run_without_submitting=True,
    )

    # With the improvements from nipreps/niworkflows#342 this truncation is now necessary
    trunc_mov = pe.Node(
        ants.ImageMath(operation="TruncateImageIntensity", op2="0.01 0.999 256"),
        name="trunc_mov",
    )

    registration = pe.Node(
        SpatialNormalization(
            float=True,
            flavor=["precise", "testing"][debug],
        ),
        name="registration",
        n_procs=omp_nthreads,
        mem_gb=2,
    )

    # Resample T1w-space inputs
    tpl_moving = pe.Node(
        ApplyTransforms(
            dimension=3,
            default_value=0,
            float=True,
            interpolation="LanczosWindowedSinc",
        ),
        name="tpl_moving",
    )

    std_mask = pe.Node(ApplyTransforms(interpolation="MultiLabel"), name="std_mask")
    std_dseg = pe.Node(ApplyTransforms(interpolation="MultiLabel"), name="std_dseg")

    std_tpms = pe.MapNode(
        ApplyTransforms(
            dimension=3, default_value=0, float=True, interpolation="Gaussian"
        ),
        iterfield=["input_image"],
        name="std_tpms",
    )

    # fmt:off
    workflow.connect([
        (inputnode, split_desc, [('template', 'template')]),
        (inputnode, poutputnode, [('template', 'template')]),
        (inputnode, trunc_mov, [('moving_image', 'op1')]),
        (inputnode, registration, [
            ('moving_mask', 'moving_mask'),
            ('lesion_mask', 'lesion_mask')]),
        (inputnode, tpl_moving, [('moving_image', 'input_image')]),
        (inputnode, std_mask, [('moving_mask', 'input_image')]),
        (split_desc, tf_select, [('name', 'template'),
                                 ('spec', 'template_spec')]),
        (split_desc, registration, [('name', 'template'),
                                    ('spec', 'template_spec')]),
        (tf_select, tpl_moving, [('t1w_file', 'reference_image')]),
        (tf_select, std_mask, [('t1w_file', 'reference_image')]),
        (tf_select, std_dseg, [('t1w_file', 'reference_image')]),
        (tf_select, std_tpms, [('t1w_file', 'reference_image')]),
        (trunc_mov, registration, [
            ('output_image', 'moving_image')]),
        (registration, tpl_moving, [('composite_transform', 'transforms')]),
        (registration, std_mask, [('composite_transform', 'transforms')]),
        (inputnode, std_dseg, [('moving_segmentation', 'input_image')]),
        (registration, std_dseg, [('composite_transform', 'transforms')]),
        (inputnode, std_tpms, [('moving_tpms', 'input_image')]),
        (registration, std_tpms, [('composite_transform', 'transforms')]),
        (registration, poutputnode, [
            ('composite_transform', 'anat2std_xfm'),
            ('inverse_composite_transform', 'std2anat_xfm')]),
        (tpl_moving, poutputnode, [('output_image', 'standardized')]),
        (std_mask, poutputnode, [('output_image', 'std_mask')]),
        (std_dseg, poutputnode, [('output_image', 'std_dseg')]),
        (std_tpms, poutputnode, [('output_image', 'std_tpms')]),
        (split_desc, poutputnode, [('spec', 'template_spec')]),
    ])
    # fmt:on

    # Provide synchronized output
    outputnode = pe.JoinNode(
        niu.IdentityInterface(fields=out_fields),
        name="outputnode",
        joinsource="inputnode",
    )
    # fmt:off
    workflow.connect([
        (poutputnode, outputnode, [(f, f) for f in out_fields]),
    ])
    # fmt:on

    return workflow

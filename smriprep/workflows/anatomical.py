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
"""Anatomical reference preprocessing workflows."""
from pkg_resources import resource_filename as pkgr

from nipype import logging
from nipype.pipeline import engine as pe
from nipype.interfaces import (
    utility as niu,
    freesurfer as fs,
    fsl,
    image,
)

from nipype.interfaces.ants.base import Info as ANTsInfo
from nipype.interfaces.ants import N4BiasFieldCorrection

from niworkflows.engine.workflows import LiterateWorkflow as Workflow
from niworkflows.interfaces.freesurfer import (
    StructuralReference,
    PatchedLTAConvert as LTAConvert,
)
from niworkflows.interfaces.header import ValidateImage
from niworkflows.interfaces.images import TemplateDimensions, Conform
from niworkflows.interfaces.nibabel import ApplyMask, Binarize
from niworkflows.interfaces.nitransforms import ConcatenateXFMs
from niworkflows.interfaces.utility import KeySelect
from niworkflows.utils.misc import add_suffix
from niworkflows.anat.ants import init_brain_extraction_wf, init_n4_only_wf
from ..utils.misc import apply_lut as _apply_bids_lut, fs_isRunning as _fs_isRunning
from .fit.registration import init_register_template_wf
from .outputs import (
    init_anat_reports_wf, init_anat_first_derivatives_wf, init_anat_second_derivatives_wf
)
from .surfaces import init_surface_derivatives_wf, init_surface_recon_wf, init_refinement_wf

LOGGER = logging.getLogger("nipype.workflow")


def init_anat_preproc_wf(
    *,
    bids_root,
    output_dir,
    freesurfer,
    hires,
    longitudinal,
    skull_strip_mode,
    skull_strip_template,
    spaces,
    t1w,
    precomputed,
    debug,
    omp_nthreads,
    name="anat_preproc_wf",
    skull_strip_fixed_seed=False,
):
    workflow = Workflow(name=name)

    inputnode = pe.Node(
        niu.IdentityInterface(
            fields=["t1w", "t2w", "roi", "flair", "subjects_dir", "subject_id"]
        ),
        name="inputnode",
    )
    outputnode = pe.Node(
        niu.IdentityInterface(
            fields=[
                "template",
                "subjects_dir",
                "subject_id",
                "t1w_preproc",
                "t1w_mask",
                "t1w_dseg",
                "t1w_tpms",
                "t1w_realign_xfm",
                "anat2std_xfm",
                "fsnative2t1w_xfm",
            ]
        ),
        name="outputnode",
    )

    # anat_preproc
    #   \- fit -\
    #            \- deriv1
    #
    #

    anat_fit_wf = init_anat_fit_wf(
        bids_root=bids_root,
        freesurfer=freesurfer,
        hires=hires,
        longitudinal=longitudinal,
        skull_strip_mode=skull_strip_mode,
        skull_strip_template=skull_strip_template,
        spaces=spaces,
        t1w=t1w,
        precomputed=precomputed,
        debug=debug,
        omp_nthreads=omp_nthreads,
        skull_strip_fixed_seed=skull_strip_fixed_seed,
    )
    anat_first_derivatives_wf = init_anat_first_derivatives_wf(
        bids_root=bids_root,
        freesurfer=freesurfer,
        num_t1w=len(t1w),
        output_dir=output_dir,
        spaces=spaces,
    )
    anat_second_derivatives_wf = init_anat_second_derivatives_wf(
        bids_root=bids_root,
        freesurfer=freesurfer,
        output_dir=output_dir,
        spaces=spaces,
    )
    # fmt:off
    workflow.connect([
        (inputnode, anat_fit_wf, [
            ("t1w", "inputnode.t1w"),
            ("t2w", "inputnode.t2w"),
            ("roi", "inputnode.roi"),
            ("flair", "inputnode.flair"),
            ("subjects_dir", "inputnode.subjects_dir"),
            ("subject_id", "inputnode.subject_id"),
        ]),
        (anat_fit_wf, outputnode, [
            ("outputnode.template", "template"),
            ("outputnode.subjects_dir", "subjects_dir"),
            ("outputnode.subject_id", "subject_id"),
            ("outputnode.t1w_preproc", "t1w_preproc"),
            ("outputnode.t1w_mask", "t1w_mask"),
            ("outputnode.t1w_dseg", "t1w_dseg"),
            ("outputnode.t1w_tpms", "t1w_tpms"),
            ("outputnode.anat2std_xfm", "anat2std_xfm"),
            ("outputnode.fsnative2t1w_xfm", "fsnative2t1w_xfm"),
        ]),
        (anat_fit_wf, anat_first_derivatives_wf, [
            ("outputnode.t1w_preproc", "inputnode.t1w_preproc"),
            ("outputnode.t1w_mask", "inputnode.t1w_mask"),
            ("outputnode.t1w_dseg", "inputnode.t1w_dseg"),
            ("outputnode.t1w_tpms", "inputnode.t1w_tpms"),
            ("outputnode.t1w_valid_list", "inputnode.source_files"),
            ("outputnode.t1w_realign_xfm", "inputnode.t1w_ref_xfms"),
            ("outputnode.template", "inputnode.template"),
            ("outputnode.anat2std_xfm", "inputnode.anat2std_xfm"),
            ("outputnode.std2anat_xfm", "inputnode.std2anat_xfm"),
            ("outputnode.fsnative2t1w_xfm", "inputnode.fsnative2t1w_xfm"),
        ]),
        (anat_fit_wf, anat_second_derivatives_wf, [
            ('outputnode.template', 'inputnode.template'),
            ('outputnode.t1w_valid_list', 'inputnode.source_files'),
            ("outputnode.t1w_preproc", "inputnode.t1w_preproc"),
            ("outputnode.t1w_mask", "inputnode.t1w_mask"),
            ("outputnode.t1w_dseg", "inputnode.t1w_dseg"),
            ("outputnode.t1w_tpms", "inputnode.t1w_tpms"),
            ('outputnode.anat2std_xfm', 'inputnode.anat2std_xfm'),
        ]),
    ])
    # fmt:on
    if freesurfer:
        surface_derivatives_wf = init_surface_derivatives_wf()
        # fmt:off
        workflow.connect([
            (anat_fit_wf, surface_derivatives_wf, [
                ('outputnode.t1w_preproc', 'inputnode.reference'),
                ('outputnode.subjects_dir', 'inputnode.subjects_dir'),
                ('outputnode.subject_id', 'inputnode.subject_id'),
                ('outputnode.fsnative2t1w_xfm', 'inputnode.fsnative2t1w_xfm'),
            ]),
            (surface_derivatives_wf, anat_second_derivatives_wf, [
                ('outputnode.surfaces', 'inputnode.surfaces'),
                ('outputnode.morphometrics', 'inputnode.morphometrics'),
                ('outputnode.out_aseg', 'inputnode.t1w_fs_aseg'),
                ('outputnode.out_aparc', 'inputnode.t1w_fs_aparc'),
            ]),
        ])
        # fmt:on

    return workflow


def init_anat_fit_wf(
    *,
    bids_root,
    freesurfer,
    hires,
    longitudinal,
    skull_strip_mode,
    skull_strip_template,
    spaces,
    t1w,
    precomputed: dict,
    debug: bool,
    omp_nthreads: int,
    name="fit_wf",
    skull_strip_fixed_seed=False,
):
    workflow = Workflow(name=name)

    num_t1w = len(t1w)

    have_t1w = "t1w_preproc" in precomputed
    have_mask = "t1w_mask" in precomputed
    have_dseg = "t1w_dseg" in precomputed
    have_tpms = "t1w_tpms" in precomputed
    # registrations = precomputed.get("anat2std_xfm", [])

    inputnode = pe.Node(
        niu.IdentityInterface(
            fields=["t1w", "t2w", "roi", "flair", "subjects_dir", "subject_id"]
        ),
        name="inputnode",
    )
    outputnode = pe.Node(
        niu.IdentityInterface(
            fields=[
                # Primary derivatives
                "t1w_preproc",
                "t1w_mask",
                "t1w_dseg",
                "t1w_tpms",
                "t1w_realign_xfm",
                "anat2std_xfm",
                "fsnative2t1w_xfm",
                # Reverse transform; not computable from forward transform
                "std2anat_xfm",
                # Metadata
                "template",
                "subjects_dir",
                "subject_id",
                "t1w_valid_list",
            ]
        ),
        name="outputnode",
    )

    # Stage 2 results
    t1w_buffer = pe.Node(
        niu.IdentityInterface(fields=["t1w_preproc", "t1w_mask", "t1w_brain", "ants_seg"]),
        name="t1w_buffer"
    )
    # Refined stage 2 results; may be direct copy if no refinement
    refined_buffer = pe.Node(
        niu.IdentityInterface(fields=["t1w_mask", "t1w_brain"]),
        name="refined_buffer"
    )
    seg_buffer = pe.Node(niu.IdentityInterface(fields=["t1w_dseg", "t1w_tpms"]), name="seg_buffer")

    # fmt:off
    workflow.connect([
        (t1w_buffer, outputnode, [("t1w_preproc", "t1w_preproc")]),
        (refined_buffer, outputnode, [("t1w_mask", "t1w_mask")]),
        (seg_buffer, outputnode, [
            ("t1w_dseg", "t1w_dseg"),
            ("t1w_tpms", "t1w_tpms"),
        ]),
    ])
    # fmt:on

    # Stage 1: Conform images and validate
    # If desc-preproc_T1w.nii.gz is provided, just validate it
    anat_validate = pe.Node(ValidateImage(), name="anat_validate", run_without_submitting=True)
    if not have_t1w:
        LOGGER.info("Stage 1: Adding template workflow")
        anat_template_wf = init_anat_template_wf(
            longitudinal=longitudinal, omp_nthreads=omp_nthreads, num_t1w=num_t1w
        )
        # fmt:off
        workflow.connect([
            (inputnode, anat_template_wf, [("t1w", "inputnode.t1w")]),
            (anat_template_wf, anat_validate, [("outputnode.t1w_ref", "in_file")]),
            (anat_template_wf, outputnode, [
                ("outputnode.t1w_valid_list", "t1w_valid_list"),
                ("outputnode.t1w_realign_xfm", "t1w_realign_xfm"),
            ]),
        ])
        # fmt:on
    else:
        LOGGER.info("Found preprocessed T1w - skipping Stage 1")
        anat_validate.inputs.in_file = precomputed["t1w_preproc"]
        outputnode.inputs.t1w_valid_list = [precomputed["t1w_preproc"]]
        workflow.connect([(anat_validate, t1w_buffer, [("out_file", "t1w_preproc")])])

    # Stage 2: INU correction and masking
    # We always need to generate t1w_brain; how to do that depends on whether we have
    # a pre-corrected T1w or precomputed mask, or are given an already masked image
    if not have_mask:
        LOGGER.info("Stage 2: Preparing brain extraction workflow")
        if skull_strip_mode == "auto":
            skull_strip_mode = all(_is_skull_stripped(img) for img in t1w)

        # Brain extraction
        if skull_strip_mode is False:
            brain_extraction_wf = init_brain_extraction_wf(
                in_template=skull_strip_template.space,
                template_spec=skull_strip_template.spec,
                atropos_use_random_seed=not skull_strip_fixed_seed,
                omp_nthreads=omp_nthreads,
                normalization_quality="precise" if not debug else "testing",
            )
            # fmt:off
            workflow.connect([
                (anat_validate, brain_extraction_wf, [("out_file", "inputnode.in_files")]),
                (brain_extraction_wf, t1w_buffer, [
                    ("outputnode.out_mask", "t1w_mask"),
                    (("outputnode.out_file", _pop), "t1w_brain"),
                    ("outputnode.out_segm", "ants_seg"),
                ]),
            ])
            if not have_t1w:
                workflow.connect([
                    (brain_extraction_wf, t1w_buffer, [
                        (("outputnode.bias_corrected", _pop), "t1w_preproc"),
                    ]),
                ])
            # fmt:on
        # Determine mask from T1w and uniformize
        elif not have_t1w:
            LOGGER.info("Stage 2: Skipping skull-strip, INU-correction only")
            n4_only_wf = init_n4_only_wf(
                omp_nthreads=omp_nthreads,
                atropos_use_random_seed=not skull_strip_fixed_seed,
            )
            # fmt:off
            workflow.connect([
                (anat_validate, n4_only_wf, [("out_file", "inputnode.in_files")]),
                (n4_only_wf, t1w_buffer, [
                    (("outputnode.bias_corrected", _pop), "t1w_preproc"),
                    ("outputnode.out_mask", "t1w_mask"),
                    (("outputnode.out_file", _pop), "t1w_brain"),
                ]),
            ])
            # fmt:on
        # Binarize the already uniformized image
        else:
            LOGGER.info("Stage 2: Skipping skull-strip, generating mask from input")
            binarize = pe.Node(Binarize(thresh_low=2), name="binarize")
            # fmt:off
            workflow.connect([
                (anat_validate, binarize, [("out_file", "in_file")]),
                (anat_validate, t1w_buffer, [("out_file", "t1w_brain")]),
                (binarize, t1w_buffer, [("out_file", "t1w_mask")]),
            ])
            # fmt:on
    else:
        LOGGER.info("Found brain mask")
        t1w_buffer.inputs.t1w_mask = precomputed["t1w_mask"]
        # If we have a mask, always apply it
        apply_mask = pe.Node(ApplyMask(in_mask=precomputed["t1w_mask"]), name="apply_mask")
        workflow.connect([(anat_validate, apply_mask, [("out_file", "in_file")])])
        # Run N4 if it hasn't been pre-run
        if not have_t1w:
            LOGGER.info("Skipping skull-strip, INU-correction only")
            n4_only_wf = init_n4_only_wf(
                omp_nthreads=omp_nthreads,
                atropos_use_random_seed=not skull_strip_fixed_seed,
            )
            # fmt:off
            workflow.connect([
                (apply_mask, n4_only_wf, [("out_file", "inputnode.in_files")]),
                (n4_only_wf, t1w_buffer, [
                    (("outputnode.bias_corrected", _pop), "t1w_preproc"),
                    (("outputnode.out_file", _pop), "t1w_brain"),
                ]),
            ])
            # fmt:on
        else:
            LOGGER.info("Skipping Stage 2")
            workflow.connect([(apply_mask, t1w_buffer, [("out_file", "t1w_brain")])])

    # Stage 3: Segmentation
    if not (have_dseg and have_tpms):
        LOGGER.info("Stage 3: Preparing segmentation workflow")
        fast = pe.Node(
            fsl.FAST(segments=True, no_bias=True, probability_maps=True),
            name="fast",
            mem_gb=3,
        )
        lut_t1w_dseg = pe.Node(niu.Function(function=_apply_bids_lut), name="lut_t1w_dseg")
        lut_t1w_dseg.inputs.lut = (0, 3, 1, 2)  # Maps: 0 -> 0, 3 -> 1, 1 -> 2, 2 -> 3.
        fast2bids = pe.Node(
            niu.Function(function=_probseg_fast2bids),
            name="fast2bids",
            run_without_submitting=True,
        )
        workflow.connect([(refined_buffer, fast, [("t1w_brain", "in_files")])])

        # fmt:off
        if not have_dseg:
            workflow.connect([
                (fast, lut_t1w_dseg, [("partial_volume_map", "in_dseg")]),
                (lut_t1w_dseg, seg_buffer, [("out", "t1w_dseg")]),
            ])
        if not have_tpms:
            workflow.connect([
                (fast, fast2bids, [("partial_volume_files", "inlist")]),
                (fast2bids, seg_buffer, [("out", "t1w_tpms")]),
            ])
        # fmt:on
    else:
        LOGGER.info("Skipping Stage 3")
    if have_dseg:
        LOGGER.info("Found discrete segmentation")
        seg_buffer.inputs.t1w_dseg = precomputed["t1w_dseg"]
    if have_tpms:
        LOGGER.info("Found tissue probability maps")
        seg_buffer.inputs.t1w_tpms = precomputed["t1w_tpms"]

    # Stage 4: Normalization
    # TODO: handle pre-run registrations
    templates = spaces.get_spaces(nonstandard=False, dim=(3,))
    LOGGER.info(f"Stage 4: Preparing normalization workflow for {templates}")
    register_template_wf = init_register_template_wf(
        debug=debug,
        omp_nthreads=omp_nthreads,
        templates=templates,
    )

    # fmt:off
    workflow.connect([
        (inputnode, register_template_wf, [('roi', 'inputnode.lesion_mask')]),
        (t1w_buffer, register_template_wf, [('t1w_preproc', 'inputnode.moving_image')]),
        (refined_buffer, register_template_wf, [('t1w_mask', 'inputnode.moving_mask')]),
        (register_template_wf, outputnode, [
            ('outputnode.template', 'template'),
            ('outputnode.anat2std_xfm', 'anat2std_xfm'),
            ('outputnode.std2anat_xfm', 'std2anat_xfm'),
        ]),
    ])
    # fmt:on

    # Do not attempt refinement (Stage 6, below)
    if have_mask or not freesurfer:
        # fmt:off
        workflow.connect([
            (t1w_buffer, refined_buffer, [
                ("t1w_mask", "t1w_mask"),
                ("t1w_brain", "t1w_brain"),
            ]),
        ])
        # fmt:on

    if not freesurfer:
        LOGGER.info("Skipping Stages 5 and 6")
        return workflow

    fs_isrunning = pe.Node(
        niu.Function(function=_fs_isRunning), overwrite=True, name="fs_isrunning"
    )
    fs_isrunning.inputs.logger = LOGGER

    # Stage 5: Surface reconstruction (--fs-no-reconall not set)
    LOGGER.info("Stage 5: Preparing surface reconstruction workflow")
    surface_recon_wf = init_surface_recon_wf(
        name="surface_recon_wf", omp_nthreads=omp_nthreads, hires=hires
    )

    # fmt:off
    workflow.connect([
        (inputnode, fs_isrunning, [
            ('subjects_dir', 'subjects_dir'),
            ('subject_id', 'subject_id'),
        ]),
        (inputnode, surface_recon_wf, [
            ('t2w', 'inputnode.t2w'),
            ('flair', 'inputnode.flair'),
            ('subject_id', 'inputnode.subject_id'),
        ]),
        (fs_isrunning, surface_recon_wf, [('out', 'inputnode.subjects_dir')]),
        (anat_validate, surface_recon_wf, [('out_file', 'inputnode.t1w')]),
        (t1w_buffer, surface_recon_wf, [('t1w_brain', 'inputnode.skullstripped_t1')]),
        (surface_recon_wf, outputnode, [
            ('outputnode.subjects_dir', 'subjects_dir'),
            ('outputnode.subject_id', 'subject_id'),
            ('outputnode.fsnative2t1w_xfm', 'fsnative2t1w_xfm'),
        ]),
    ])
    # fmt:on

    if not have_mask:
        LOGGER.info("Stage 6: Preparing mask refinement workflow")
        # Stage 6: Refine ANTs mask with FreeSurfer segmentation
        refinement_wf = init_refinement_wf()
        applyrefined = pe.Node(fsl.ApplyMask(), name="applyrefined")

        # fmt:off
        workflow.connect([
            (surface_recon_wf, refinement_wf, [
                ('outputnode.subjects_dir', 'inputnode.subjects_dir'),
                ('outputnode.subject_id', 'inputnode.subject_id'),
                ('outputnode.fsnative2t1w_xfm', 'inputnode.fsnative2t1w_xfm'),
            ]),
            (t1w_buffer, refinement_wf, [
                ('t1w_preproc', 'inputnode.reference_image'),
                ('ants_seg', 'inputnode.ants_segs'),
            ]),
            (t1w_buffer, applyrefined, [('t1w_preproc', 'in_file')]),
            (refinement_wf, applyrefined, [('outputnode.out_brainmask', 'mask_file')]),
            (refinement_wf, refined_buffer, [('outputnode.out_brainmask', 't1w_mask')]),
            (applyrefined, refined_buffer, [('out_file', 't1w_brain')]),
        ])
        # fmt:on
    else:
        LOGGER.info("Found brain mask - skipping Stage 6")

    return workflow


def init_anat_template_wf(
    *, longitudinal, omp_nthreads, num_t1w, name="anat_template_wf"
):
    """
    Generate a canonically-oriented, structural average from all input T1w images.

    Workflow Graph
        .. workflow::
            :graph2use: orig
            :simple_form: yes

            from smriprep.workflows.anatomical import init_anat_template_wf
            wf = init_anat_template_wf(
                longitudinal=False, omp_nthreads=1, num_t1w=1)

    Parameters
    ----------
    longitudinal : :obj:`bool`
        Create unbiased structural average, regardless of number of inputs
        (may increase runtime)
    omp_nthreads : :obj:`int`
        Maximum number of threads an individual process may use
    num_t1w : :obj:`int`
        Number of T1w images
    name : :obj:`str`, optional
        Workflow name (default: anat_template_wf)

    Inputs
    ------
    t1w
        List of T1-weighted structural images

    Outputs
    -------
    t1w_ref
        Structural reference averaging input T1w images, defining the T1w space.
    t1w_realign_xfm
        List of affine transforms to realign input T1w images
    out_report
        Conformation report

    """
    workflow = Workflow(name=name)

    if num_t1w > 1:
        workflow.__desc__ = """\
A T1w-reference map was computed after registration of
{num_t1w} T1w images (after INU-correction) using
`mri_robust_template` [FreeSurfer {fs_ver}, @fs_template].
""".format(
            num_t1w=num_t1w, fs_ver=fs.Info().looseversion() or "<ver>"
        )

    inputnode = pe.Node(niu.IdentityInterface(fields=["t1w"]), name="inputnode")
    outputnode = pe.Node(
        niu.IdentityInterface(
            fields=["t1w_ref", "t1w_valid_list", "t1w_realign_xfm", "out_report"]
        ),
        name="outputnode",
    )

    # 0. Reorient T1w image(s) to RAS and resample to common voxel space
    t1w_ref_dimensions = pe.Node(TemplateDimensions(), name="t1w_ref_dimensions")
    t1w_conform = pe.MapNode(Conform(), iterfield="in_file", name="t1w_conform")

    # fmt:off
    workflow.connect([
        (inputnode, t1w_ref_dimensions, [('t1w', 't1w_list')]),
        (t1w_ref_dimensions, t1w_conform, [
            ('t1w_valid_list', 'in_file'),
            ('target_zooms', 'target_zooms'),
            ('target_shape', 'target_shape')]),
        (t1w_ref_dimensions, outputnode, [('out_report', 'out_report'),
                                          ('t1w_valid_list', 't1w_valid_list')]),
    ])
    # fmt:on

    if num_t1w == 1:
        get1st = pe.Node(niu.Select(index=[0]), name="get1st")
        outputnode.inputs.t1w_realign_xfm = [
            pkgr("smriprep", "data/itkIdentityTransform.txt")
        ]

        # fmt:off
        workflow.connect([
            (t1w_conform, get1st, [('out_file', 'inlist')]),
            (get1st, outputnode, [('out', 't1w_ref')]),
        ])
        # fmt:on
        return workflow

    t1w_conform_xfm = pe.MapNode(
        LTAConvert(in_lta="identity.nofile", out_lta=True),
        iterfield=["source_file", "target_file"],
        name="t1w_conform_xfm",
    )

    # 1. Template (only if several T1w images)
    # 1a. Correct for bias field: the bias field is an additive factor
    #     in log-transformed intensity units. Therefore, it is not a linear
    #     combination of fields and N4 fails with merged images.
    # 1b. Align and merge if several T1w images are provided
    n4_correct = pe.MapNode(
        N4BiasFieldCorrection(dimension=3, copy_header=True),
        iterfield="input_image",
        name="n4_correct",
        n_procs=1,
    )  # n_procs=1 for reproducibility
    # StructuralReference is fs.RobustTemplate if > 1 volume, copying otherwise
    t1w_merge = pe.Node(
        StructuralReference(
            auto_detect_sensitivity=True,
            initial_timepoint=1,  # For deterministic behavior
            intensity_scaling=True,  # 7-DOF (rigid + intensity)
            subsample_threshold=200,
            fixed_timepoint=not longitudinal,
            no_iteration=not longitudinal,
            transform_outputs=True,
        ),
        mem_gb=2 * num_t1w - 1,
        name="t1w_merge",
    )

    # 2. Reorient template to RAS, if needed (mri_robust_template may set to LIA)
    t1w_reorient = pe.Node(image.Reorient(), name="t1w_reorient")

    merge_xfm = pe.MapNode(
        niu.Merge(2),
        name="merge_xfm",
        iterfield=["in1", "in2"],
        run_without_submitting=True,
    )
    concat_xfms = pe.MapNode(
        ConcatenateXFMs(inverse=True),
        name="concat_xfms",
        iterfield=["in_xfms"],
        run_without_submitting=True,
    )

    def _set_threads(in_list, maximum):
        return min(len(in_list), maximum)

    # fmt:off
    workflow.connect([
        (t1w_ref_dimensions, t1w_conform_xfm, [('t1w_valid_list', 'source_file')]),
        (t1w_conform, t1w_conform_xfm, [('out_file', 'target_file')]),
        (t1w_conform, n4_correct, [('out_file', 'input_image')]),
        (t1w_conform, t1w_merge, [
            (('out_file', _set_threads, omp_nthreads), 'num_threads'),
            (('out_file', add_suffix, '_template'), 'out_file')]),
        (n4_correct, t1w_merge, [('output_image', 'in_files')]),
        (t1w_merge, t1w_reorient, [('out_file', 'in_file')]),
        # Combine orientation and template transforms
        (t1w_conform_xfm, merge_xfm, [('out_lta', 'in1')]),
        (t1w_merge, merge_xfm, [('transform_outputs', 'in2')]),
        (merge_xfm, concat_xfms, [('out', 'in_xfms')]),
        # Output
        (t1w_reorient, outputnode, [('out_file', 't1w_ref')]),
        (concat_xfms, outputnode, [('out_xfm', 't1w_realign_xfm')]),
    ])
    # fmt:on
    return workflow


def _pop(inlist):
    if isinstance(inlist, (list, tuple)):
        return inlist[0]
    return inlist


def _aseg_to_three():
    """
    Map FreeSurfer's segmentation onto a brain (3-)tissue segmentation.

    This function generates an index of 255+0 labels and maps them into zero (bg),
    1 (GM), 2 (WM), or 3 (CSF). The new values are set according to BIDS-Derivatives.
    Then the index is populated (e.g., label 3 in the original segmentation maps to label
    1 in the output).
    The `aseg lookup table
    <https://github.com/freesurfer/freesurfer/blob/2beb96c6099d96508246c14a24136863124566a3/distribution/ASegStatsLUT.txt>`__
    is available in the FreeSurfer source.

    """
    import numpy as np

    # Base struct
    aseg_lut = np.zeros((256,), dtype="int")
    # GM
    aseg_lut[3] = 1
    aseg_lut[8:14] = 1
    aseg_lut[17:21] = 1
    aseg_lut[26:40] = 1
    aseg_lut[42] = 1
    aseg_lut[47:73] = 1

    # CSF
    aseg_lut[4:6] = 3
    aseg_lut[14:16] = 3
    aseg_lut[24] = 3
    aseg_lut[43:45] = 3
    aseg_lut[72] = 3

    # WM
    aseg_lut[2] = 2
    aseg_lut[7] = 2
    aseg_lut[16] = 2
    aseg_lut[28] = 2
    aseg_lut[41] = 2
    aseg_lut[46] = 2
    aseg_lut[60] = 2
    aseg_lut[77:80] = 2
    aseg_lut[250:256] = 2
    return tuple(aseg_lut)


def _split_segments(in_file):
    from pathlib import Path
    import numpy as np
    import nibabel as nb

    segimg = nb.load(in_file)
    data = np.int16(segimg.dataobj)
    hdr = segimg.header.copy()
    hdr.set_data_dtype("uint8")

    out_files = []
    for i, label in enumerate(("GM", "WM", "CSF"), 1):
        out_fname = str(Path.cwd() / f"aseg_label-{label}_mask.nii.gz")
        segimg.__class__(data == i, segimg.affine, hdr).to_filename(out_fname)
        out_files.append(out_fname)

    return out_files


def _probseg_fast2bids(inlist):
    """Reorder a list of probseg maps from FAST (CSF, WM, GM) to BIDS (GM, WM, CSF)."""
    return (inlist[1], inlist[2], inlist[0])


def _is_skull_stripped(img):
    """Check if T1w images are skull-stripped."""
    import nibabel as nb
    import numpy as np

    data = nb.load(img).dataobj
    sidevals = (
        np.abs(data[0, :, :]).sum()
        + np.abs(data[-1, :, :]).sum()
        + np.abs(data[:, 0, :]).sum()
        + np.abs(data[:, -1, :]).sum()
        + np.abs(data[:, :, 0]).sum()
        + np.abs(data[:, :, -1]).sum()
    )
    return sidevals < 10

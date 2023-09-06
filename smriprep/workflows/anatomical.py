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
import typing as ty

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
from nipype.interfaces.ants import DenoiseImage, N4BiasFieldCorrection

from niworkflows.engine.workflows import LiterateWorkflow as Workflow
from niworkflows.interfaces.fixes import FixHeaderApplyTransforms as ApplyTransforms
from niworkflows.interfaces.freesurfer import (
    StructuralReference,
    PatchedLTAConvert as LTAConvert,
)
from niworkflows.interfaces.header import ValidateImage
from niworkflows.interfaces.images import TemplateDimensions, Conform
from niworkflows.interfaces.nibabel import ApplyMask, Binarize
from niworkflows.interfaces.nitransforms import ConcatenateXFMs
from niworkflows.utils.spaces import SpatialReferences, Reference
from niworkflows.utils.misc import add_suffix
from niworkflows.anat.ants import init_brain_extraction_wf, init_n4_only_wf
from ..interfaces import DerivativesDataSink
from ..utils.misc import apply_lut as _apply_bids_lut, fs_isRunning as _fs_isRunning
from .fit.registration import init_register_template_wf
from .outputs import (
    init_anat_reports_wf,
    init_ds_surfaces_wf,
    init_ds_template_wf,
    init_ds_mask_wf,
    init_ds_dseg_wf,
    init_ds_tpms_wf,
    init_ds_template_registration_wf,
    init_ds_fs_registration_wf,
    init_anat_second_derivatives_wf,
)
from .surfaces import (
    init_anat_ribbon_wf,
    init_surface_derivatives_wf,
    init_surface_recon_wf,
    init_refinement_wf,
)

LOGGER = logging.getLogger("nipype.workflow")


def init_anat_preproc_wf(
    *,
    bids_root: str,
    output_dir: str,
    freesurfer: bool,
    hires: bool,
    longitudinal: bool,
    msm_sulc: bool,
    t1w: list,
    t2w: list,
    skull_strip_mode: str,
    skull_strip_template: Reference,
    spaces: SpatialReferences,
    precomputed: dict,
    omp_nthreads: int,
    debug: bool = False,
    sloppy: bool = False,
    cifti_output: ty.Literal["91k", "170k", False] = False,
    name: str = "anat_preproc_wf",
    skull_strip_fixed_seed: bool = False,
):
    """
    Stage the anatomical preprocessing steps of *sMRIPrep*.

    This workflow is a compatibility wrapper around :py:func:`init_anat_fit_wf`
    that emits all derivatives that were present in sMRIPrep 0.9.x and before.

    Workflow Graph
        .. workflow::
            :graph2use: orig
            :simple_form: yes

            from niworkflows.utils.spaces import SpatialReferences, Reference
            from smriprep.workflows.anatomical import init_anat_preproc_wf
            wf = init_anat_preproc_wf(
                bids_root='.',
                output_dir='.',
                freesurfer=True,
                hires=True,
                longitudinal=False,
                msm_sulc=False,
                t1w=['t1w.nii.gz'],
                t2w=[],
                skull_strip_mode='force',
                skull_strip_template=Reference('OASIS30ANTs'),
                spaces=SpatialReferences(spaces=['MNI152NLin2009cAsym', 'fsaverage5']),
                precomputed={},
                omp_nthreads=1,
            )


    Parameters
    ----------
    bids_root : :obj:`str`
        Path of the input BIDS dataset root
    output_dir : :obj:`str`
        Directory in which to save derivatives
    freesurfer : :obj:`bool`
        Enable FreeSurfer surface reconstruction (increases runtime by 6h,
        at the very least)
    hires : :obj:`bool`
        Enable sub-millimeter preprocessing in FreeSurfer
    longitudinal : :obj:`bool`
        Create unbiased structural template, regardless of number of inputs
        (may increase runtime)
    t1w : :obj:`list`
        List of T1-weighted structural images.
    skull_strip_mode : :obj:`str`
        Determiner for T1-weighted skull stripping (`force` ensures skull stripping,
        `skip` ignores skull stripping, and `auto` automatically ignores skull stripping
        if pre-stripped brains are detected).
    skull_strip_template : :py:class:`~niworkflows.utils.spaces.Reference`
        Spatial reference to use in atlas-based brain extraction.
    spaces : :py:class:`~niworkflows.utils.spaces.SpatialReferences`
        Object containing standard and nonstandard space specifications.
    precomputed : :obj:`dict`
        Dictionary mapping output specification attribute names and
        paths to precomputed derivatives.
    omp_nthreads : :obj:`int`
        Maximum number of threads an individual process may use
    debug : :obj:`bool`
        Enable debugging outputs
    sloppy: :obj:`bool`
        Quick, impercise operations. Used to decrease workflow duration.
    name : :obj:`str`, optional
        Workflow name (default: anat_fit_wf)
    skull_strip_fixed_seed : :obj:`bool`
        Do not use a random seed for skull-stripping - will ensure
        run-to-run replicability when used with --omp-nthreads 1
        (default: ``False``).

    Inputs
    ------
    t1w
        List of T1-weighted structural images
    t2w
        List of T2-weighted structural images
    roi
        A mask to exclude regions during standardization
    flair
        List of FLAIR images
    subjects_dir
        FreeSurfer SUBJECTS_DIR
    subject_id
        FreeSurfer subject ID

    Outputs
    -------
    t1w_preproc
        The T1w reference map, which is calculated as the average of bias-corrected
        and preprocessed T1w images, defining the anatomical space.
    t1w_mask
        Brain (binary) mask estimated by brain extraction.
    t1w_dseg
        Brain tissue segmentation of the preprocessed structural image, including
        gray-matter (GM), white-matter (WM) and cerebrospinal fluid (CSF).
    t1w_tpms
        List of tissue probability maps corresponding to ``t1w_dseg``.
    template
        List of template names to which the structural image has been registered
    anat2std_xfm
        List of nonlinear spatial transforms to resample data from subject
        anatomical space into standard template spaces. Collated with template.
    std2anat_xfm
        List of nonlinear spatial transforms to resample data from standard
        template spaces into subject anatomical space. Collated with template.
    subjects_dir
        FreeSurfer SUBJECTS_DIR; use as input to a node to ensure that it is run after
        FreeSurfer reconstruction is completed.
    subject_id
        FreeSurfer subject ID; use as input to a node to ensure that it is run after
        FreeSurfer reconstruction is completed.
    fsnative2t1w_xfm
        ITK-style affine matrix translating from FreeSurfer-conformed subject space to T1w

    """
    workflow = Workflow(name=name)

    inputnode = pe.Node(
        niu.IdentityInterface(fields=["t1w", "t2w", "roi", "flair", "subjects_dir", "subject_id"]),
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
                "anat2std_xfm",
                "std2anat_xfm",
                "fsnative2t1w_xfm",
                "t1w_aparc",
                "t1w_aseg",
                "sphere_reg",
                "sphere_reg_fsLR",
            ]
        ),
        name="outputnode",
    )

    anat_fit_wf = init_anat_fit_wf(
        bids_root=bids_root,
        output_dir=output_dir,
        freesurfer=freesurfer,
        hires=hires,
        longitudinal=longitudinal,
        skull_strip_mode=skull_strip_mode,
        skull_strip_template=skull_strip_template,
        spaces=spaces,
        t1w=t1w,
        t2w=t2w,
        precomputed=precomputed,
        debug=debug,
        sloppy=sloppy,
        omp_nthreads=omp_nthreads,
        skull_strip_fixed_seed=skull_strip_fixed_seed,
    )
    anat_second_derivatives_wf = init_anat_second_derivatives_wf(
        bids_root=bids_root,
        freesurfer=freesurfer,
        output_dir=output_dir,
        spaces=spaces,
        cifti_output=cifti_output,
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
            ("outputnode.std2anat_xfm", "std2anat_xfm"),
            ("outputnode.fsnative2t1w_xfm", "fsnative2t1w_xfm"),
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
        surfaces = ["white", "pial", "midthickness", "inflated", "sphere_reg", "sphere_reg_fsLR"]
        if msm_sulc:
            surfaces.append("sphere_reg_msm")

        surface_derivatives_wf = init_surface_derivatives_wf(
            msm_sulc=msm_sulc,
            cifti_output=cifti_output,
            sloppy=sloppy,
        )
        anat_ribbon_wf = init_anat_ribbon_wf()
        ds_surfaces_wf = init_ds_surfaces_wf(
            bids_root=bids_root, output_dir=output_dir, surfaces=surfaces
        )

        # fmt:off
        workflow.connect([
            (anat_fit_wf, surface_derivatives_wf, [
                ('outputnode.t1w_preproc', 'inputnode.reference'),
                ('outputnode.subjects_dir', 'inputnode.subjects_dir'),
                ('outputnode.subject_id', 'inputnode.subject_id'),
                ('outputnode.fsnative2t1w_xfm', 'inputnode.fsnative2t1w_xfm'),
            ]),
            (anat_fit_wf, anat_ribbon_wf, [
                ('outputnode.t1w_mask', 'inputnode.ref_file'),
            ]),
            (surface_derivatives_wf, anat_ribbon_wf, [
                ('outputnode.white', 'inputnode.white'),
                ('outputnode.pial', 'inputnode.pial'),
            ]),
            (anat_fit_wf, ds_surfaces_wf, [
                ('outputnode.t1w_valid_list', 'inputnode.source_files'),
            ]),
            (surface_derivatives_wf, ds_surfaces_wf, [
                (f'outputnode.{surface}', f'inputnode.{surface}')
                for surface in surfaces
            ]),
            (surface_derivatives_wf, anat_second_derivatives_wf, [
                ('outputnode.morphometrics', 'inputnode.morphometrics'),
                ('outputnode.out_aseg', 'inputnode.t1w_fs_aseg'),
                ('outputnode.out_aparc', 'inputnode.t1w_fs_aparc'),
                ('outputnode.cifti_morph', 'inputnode.cifti_morph'),
                ('outputnode.cifti_metadata', 'inputnode.cifti_metadata'),
            ]),
            (surface_derivatives_wf, outputnode, [
                ('outputnode.out_aseg', 't1w_aseg'),
                ('outputnode.out_aparc', 't1w_aparc'),
                ('outputnode.sphere_reg', 'sphere_reg'),
                ('outputnode.sphere_reg_fsLR', 'sphere_reg_fsLR'),
            ]),
            (anat_ribbon_wf, outputnode, [
                ("outputnode.anat_ribbon", "anat_ribbon"),
            ]),
            (anat_ribbon_wf, anat_second_derivatives_wf, [
                ("outputnode.anat_ribbon", "inputnode.anat_ribbon"),
            ]),
        ])
        # fmt:on

    return workflow


def init_anat_fit_wf(
    *,
    bids_root: str,
    output_dir: str,
    freesurfer: bool,
    hires: bool,
    longitudinal: bool,
    t1w: list,
    t2w: list,
    skull_strip_mode: str,
    skull_strip_template: Reference,
    spaces: SpatialReferences,
    precomputed: dict,
    omp_nthreads: int,
    debug: bool = False,
    sloppy: bool = False,
    name="anat_fit_wf",
    skull_strip_fixed_seed: bool = False,
):
    """
    Stage the anatomical preprocessing steps of *sMRIPrep*.

    This includes:

      - T1w reference: realigning and then averaging T1w images.
      - Brain extraction and INU (bias field) correction.
      - Brain tissue segmentation.
      - Spatial normalization to standard spaces.
      - Surface reconstruction with FreeSurfer_.

    .. include:: ../links.rst

    Workflow Graph
        .. workflow::
            :graph2use: orig
            :simple_form: yes

            from niworkflows.utils.spaces import SpatialReferences, Reference
            from smriprep.workflows.anatomical import init_anat_fit_wf
            wf = init_anat_fit_wf(
                bids_root='.',
                output_dir='.',
                freesurfer=True,
                hires=True,
                longitudinal=False,
                t1w=['t1w.nii.gz'],
                t2w=['t2w.nii.gz'],
                skull_strip_mode='force',
                skull_strip_template=Reference('OASIS30ANTs'),
                spaces=SpatialReferences(spaces=['MNI152NLin2009cAsym', 'fsaverage5']),
                precomputed={},
                debug=False,
                sloppy=False,
                omp_nthreads=1,
            )


    Parameters
    ----------
    bids_root : :obj:`str`
        Path of the input BIDS dataset root
    output_dir : :obj:`str`
        Directory in which to save derivatives
    freesurfer : :obj:`bool`
        Enable FreeSurfer surface reconstruction (increases runtime by 6h,
        at the very least)
    hires : :obj:`bool`
        Enable sub-millimeter preprocessing in FreeSurfer
    longitudinal : :obj:`bool`
        Create unbiased structural template, regardless of number of inputs
        (may increase runtime)
    t1w : :obj:`list`
        List of T1-weighted structural images.
    skull_strip_mode : :obj:`str`
        Determiner for T1-weighted skull stripping (`force` ensures skull stripping,
        `skip` ignores skull stripping, and `auto` automatically ignores skull stripping
        if pre-stripped brains are detected).
    skull_strip_template : :py:class:`~niworkflows.utils.spaces.Reference`
        Spatial reference to use in atlas-based brain extraction.
    spaces : :py:class:`~niworkflows.utils.spaces.SpatialReferences`
        Object containing standard and nonstandard space specifications.
    precomputed : :obj:`dict`
        Dictionary mapping output specification attribute names and
        paths to precomputed derivatives.
    omp_nthreads : :obj:`int`
        Maximum number of threads an individual process may use
    debug : :obj:`bool`
        Enable debugging outputs
    sloppy: :obj:`bool`
        Quick, impercise operations. Used to decrease workflow duration.
    name : :obj:`str`, optional
        Workflow name (default: anat_fit_wf)
    skull_strip_fixed_seed : :obj:`bool`
        Do not use a random seed for skull-stripping - will ensure
        run-to-run replicability when used with --omp-nthreads 1
        (default: ``False``).

    Inputs
    ------
    t1w
        List of T1-weighted structural images
    t2w
        List of T2-weighted structural images
    roi
        A mask to exclude regions during standardization
    flair
        List of FLAIR images
    subjects_dir
        FreeSurfer SUBJECTS_DIR
    subject_id
        FreeSurfer subject ID

    Outputs
    -------
    t1w_preproc
        The T1w reference map, which is calculated as the average of bias-corrected
        and preprocessed T1w images, defining the anatomical space.
    t1w_mask
        Brain (binary) mask estimated by brain extraction.
    t1w_dseg
        Brain tissue segmentation of the preprocessed structural image, including
        gray-matter (GM), white-matter (WM) and cerebrospinal fluid (CSF).
    t1w_tpms
        List of tissue probability maps corresponding to ``t1w_dseg``.
    t1w_valid_list
        List of input T1w images accepted for preprocessing. If t1w_preproc is
        precomputed, this is always a list containing that image.
    template
        List of template names to which the structural image has been registered
    anat2std_xfm
        List of nonlinear spatial transforms to resample data from subject
        anatomical space into standard template spaces. Collated with template.
    std2anat_xfm
        List of nonlinear spatial transforms to resample data from standard
        template spaces into subject anatomical space. Collated with template.
    subjects_dir
        FreeSurfer SUBJECTS_DIR; use as input to a node to ensure that it is run after
        FreeSurfer reconstruction is completed.
    subject_id
        FreeSurfer subject ID; use as input to a node to ensure that it is run after
        FreeSurfer reconstruction is completed.
    fsnative2t1w_xfm
        ITK-style affine matrix translating from FreeSurfer-conformed subject space to T1w

    See Also
    --------
    * :py:func:`~niworkflows.anat.ants.init_brain_extraction_wf`
    * :py:func:`~smriprep.workflows.surfaces.init_surface_recon_wf`

    """
    workflow = Workflow(name=name)
    num_t1w = len(t1w)
    desc = f"""
Anatomical data preprocessing

: A total of {num_t1w} T1-weighted (T1w) images were found within the input
BIDS dataset."""

    have_t1w = "t1w_preproc" in precomputed
    have_t2w = "t2w_preproc" in precomputed
    have_mask = "t1w_mask" in precomputed
    have_dseg = "t1w_dseg" in precomputed
    have_tpms = "t1w_tpms" in precomputed

    # Organization
    # ------------
    # This workflow takes the usual (inputnode -> graph -> outputnode) format
    # The graph consists of (input -> compute -> datasink -> buffer) units,
    # and all inputs to outputnode are buffer.
    # If precomputed inputs are found, then these units are replaced with (buffer)
    #     At the time of writing, t1w_mask is an exception, which takes the form
    #     (t1w_buffer -> refined_buffer -> datasink -> outputnode)
    # All outputnode components should therefore point to files in the input or
    # output directories.
    inputnode = pe.Node(
        niu.IdentityInterface(fields=["t1w", "t2w", "roi", "flair", "subjects_dir", "subject_id"]),
        name="inputnode",
    )
    outputnode = pe.Node(
        niu.IdentityInterface(
            fields=[
                # Primary derivatives
                "t1w_preproc",
                "t2w_preproc",
                "t1w_mask",
                "t1w_dseg",
                "t1w_tpms",
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
    # If all derivatives exist, inputnode could go unconnected, so add explicitly
    workflow.add_nodes([inputnode])

    # Stage 1 inputs (filtered)
    sourcefile_buffer = pe.Node(
        niu.IdentityInterface(fields=["source_files"]),
        name="sourcefile_buffer",
    )

    # Stage 2 results
    t1w_buffer = pe.Node(
        niu.IdentityInterface(fields=["t1w_preproc", "t1w_mask", "t1w_brain", "ants_seg"]),
        name="t1w_buffer",
    )
    # Refined stage 2 results; may be direct copy if no refinement
    refined_buffer = pe.Node(
        niu.IdentityInterface(fields=["t1w_mask", "t1w_brain"]),
        name="refined_buffer",
    )
    # Stage 3 results
    seg_buffer = pe.Node(
        niu.IdentityInterface(fields=["t1w_dseg", "t1w_tpms"]),
        name="seg_buffer",
    )
    # Stage 4 results: collated template names, forward and reverse transforms
    template_buffer = pe.Node(niu.Merge(2), name="template_buffer")
    anat2std_buffer = pe.Node(niu.Merge(2), name="anat2std_buffer")
    std2anat_buffer = pe.Node(niu.Merge(2), name="std2anat_buffer")

    # fmt:off
    workflow.connect([
        (seg_buffer, outputnode, [
            ("t1w_dseg", "t1w_dseg"),
            ("t1w_tpms", "t1w_tpms"),
        ]),
        (anat2std_buffer, outputnode, [("out", "anat2std_xfm")]),
        (std2anat_buffer, outputnode, [("out", "std2anat_xfm")]),
        (template_buffer, outputnode, [("out", "template")]),
        (sourcefile_buffer, outputnode, [("source_files", "t1w_valid_list")]),
    ])
    # fmt:on

    # Reporting
    anat_reports_wf = init_anat_reports_wf(
        spaces=spaces,
        freesurfer=freesurfer,
        output_dir=output_dir,
    )
    # fmt:off
    workflow.connect([
        (outputnode, anat_reports_wf, [
            ("t1w_valid_list", "inputnode.source_file"),
            ("t1w_preproc", "inputnode.t1w_preproc"),
            ("t1w_mask", "inputnode.t1w_mask"),
            ("t1w_dseg", "inputnode.t1w_dseg"),
            ("template", "inputnode.template"),
            ("anat2std_xfm", "inputnode.anat2std_xfm"),
            ("subjects_dir", "inputnode.subjects_dir"),
            ("subject_id", "inputnode.subject_id"),
        ]),
    ])
    # fmt:on

    # Stage 1: Conform images and validate
    # If desc-preproc_T1w.nii.gz is provided, just validate it
    anat_validate = pe.Node(ValidateImage(), name="anat_validate", run_without_submitting=True)
    if not have_t1w:
        LOGGER.info("Stage 1: Adding template workflow")
        ants_ver = ANTsInfo.version() or "(version unknown)"
        desc += f"""\
 {"Each" if num_t1w > 1 else "The"} T1w image was corrected for intensity
non-uniformity (INU) with `N4BiasFieldCorrection` [@n4], distributed with ANTs {ants_ver}
[@ants, RRID:SCR_004757]"""
        desc += ".\n" if num_t1w > 1 else ", and used as T1w-reference throughout the workflow.\n"

        anat_template_wf = init_anat_template_wf(
            longitudinal=longitudinal,
            omp_nthreads=omp_nthreads,
            num_files=num_t1w,
            contrast="T1w",
            name="anat_template_wf",
        )
        ds_template_wf = init_ds_template_wf(output_dir=output_dir, num_t1w=num_t1w)

        # fmt:off
        workflow.connect([
            (inputnode, anat_template_wf, [("t1w", "inputnode.anat_files")]),
            (anat_template_wf, anat_validate, [("outputnode.anat_ref", "in_file")]),
            (anat_template_wf, sourcefile_buffer, [
                ("outputnode.anat_valid_list", "source_files"),
            ]),
            (anat_template_wf, anat_reports_wf, [
                ("outputnode.out_report", "inputnode.t1w_conform_report"),
            ]),
            (anat_template_wf, ds_template_wf, [
                ("outputnode.anat_realign_xfm", "inputnode.t1w_ref_xfms"),
            ]),
            (sourcefile_buffer, ds_template_wf, [("source_files", "inputnode.source_files")]),
            (t1w_buffer, ds_template_wf, [("t1w_preproc", "inputnode.t1w_preproc")]),
            (ds_template_wf, outputnode, [("outputnode.t1w_preproc", "t1w_preproc")]),
        ])
        # fmt:on
    else:
        LOGGER.info("Found preprocessed T1w - skipping Stage 1")
        desc += """ A preprocessed T1w image was provided as a precomputed input
and used as T1w-reference throughout the workflow.
"""

        anat_validate.inputs.in_file = precomputed["t1w_preproc"]
        sourcefile_buffer.inputs.source_files = [precomputed["t1w_preproc"]]

        # fmt:off
        workflow.connect([
            (anat_validate, t1w_buffer, [("out_file", "t1w_preproc")]),
            (t1w_buffer, outputnode, [("t1w_preproc", "t1w_preproc")]),
        ])
        # fmt:on

    # Stage 2: INU correction and masking
    # We always need to generate t1w_brain; how to do that depends on whether we have
    # a pre-corrected T1w or precomputed mask, or are given an already masked image
    if not have_mask:
        LOGGER.info("Stage 2: Preparing brain extraction workflow")
        if skull_strip_mode == "auto":
            run_skull_strip = all(_is_skull_stripped(img) for img in t1w)
        else:
            run_skull_strip = {"force": True, "skip": False}

        # Brain extraction
        if run_skull_strip:
            desc += f"""\
The T1w-reference was then skull-stripped with a *Nipype* implementation of
the `antsBrainExtraction.sh` workflow (from ANTs), using {skull_strip_template.fullname}
as target template.
"""
            brain_extraction_wf = init_brain_extraction_wf(
                in_template=skull_strip_template.space,
                template_spec=skull_strip_template.spec,
                atropos_use_random_seed=not skull_strip_fixed_seed,
                omp_nthreads=omp_nthreads,
                normalization_quality="precise" if not sloppy else "testing",
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
            desc += """\
The provided T1w image was previously skull-stripped; a brain mask was
derived from the input image.
"""
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
                    ("outputnode.out_segm", "ants_seg"),
                ]),
            ])
            # fmt:on
        # Binarize the already uniformized image
        else:
            LOGGER.info("Stage 2: Skipping skull-strip, generating mask from input")
            desc += """\
The provided T1w image was previously skull-stripped; a brain mask was
derived from the input image.
"""
            binarize = pe.Node(Binarize(thresh_low=2), name="binarize")
            # fmt:off
            workflow.connect([
                (anat_validate, binarize, [("out_file", "in_file")]),
                (anat_validate, t1w_buffer, [("out_file", "t1w_brain")]),
                (binarize, t1w_buffer, [("out_file", "t1w_mask")]),
            ])
            # fmt:on

        ds_mask_wf = init_ds_mask_wf(bids_root=bids_root, output_dir=output_dir)
        # fmt:off
        workflow.connect([
            (sourcefile_buffer, ds_mask_wf, [("source_files", "inputnode.source_files")]),
            (refined_buffer, ds_mask_wf, [("t1w_mask", "inputnode.t1w_mask")]),
            (ds_mask_wf, outputnode, [("outputnode.t1w_mask", "t1w_mask")]),
        ])
        # fmt:on
    else:
        LOGGER.info("Found brain mask")
        desc += """\
A pre-computed brain mask was provided as input and used throughout the workflow.
"""
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
        workflow.connect([(refined_buffer, outputnode, [("t1w_mask", "t1w_mask")])])

    # Stage 3: Segmentation
    if not (have_dseg and have_tpms):
        LOGGER.info("Stage 3: Preparing segmentation workflow")
        fsl_ver = fsl.FAST().version or "(version unknown)"
        desc += f"""\
Brain tissue segmentation of cerebrospinal fluid (CSF),
white-matter (WM) and gray-matter (GM) was performed on
the brain-extracted T1w using `fast` [FSL {fsl_ver}, RRID:SCR_002823, @fsl_fast].
"""
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
            ds_dseg_wf = init_ds_dseg_wf(output_dir=output_dir)
            workflow.connect([
                (fast, lut_t1w_dseg, [("partial_volume_map", "in_dseg")]),
                (sourcefile_buffer, ds_dseg_wf, [("source_files", "inputnode.source_files")]),
                (lut_t1w_dseg, ds_dseg_wf, [("out", "inputnode.t1w_dseg")]),
                (ds_dseg_wf, seg_buffer, [("outputnode.t1w_dseg", "t1w_dseg")]),
            ])
        if not have_tpms:
            ds_tpms_wf = init_ds_tpms_wf(output_dir=output_dir)
            workflow.connect([
                (fast, fast2bids, [("partial_volume_files", "inlist")]),
                (sourcefile_buffer, ds_tpms_wf, [("source_files", "inputnode.source_files")]),
                (fast2bids, ds_tpms_wf, [("out", "inputnode.t1w_tpms")]),
                (ds_tpms_wf, seg_buffer, [("outputnode.t1w_tpms", "t1w_tpms")]),
            ])
        # fmt:on
    else:
        LOGGER.info("Skipping Stage 3")
    if have_dseg:
        LOGGER.info("Found discrete segmentation")
        desc += "Precomputed discrete tissue segmentations were provided as inputs.\n"
        seg_buffer.inputs.t1w_dseg = precomputed["t1w_dseg"]
    if have_tpms:
        LOGGER.info("Found tissue probability maps")
        desc += "Precomputed tissue probabiilty maps were provided as inputs.\n"
        seg_buffer.inputs.t1w_tpms = precomputed["t1w_tpms"]

    # Stage 4: Normalization
    templates = []
    found_xfms = {}
    for template in spaces.get_spaces(nonstandard=False, dim=(3,)):
        xfms = precomputed.get("transforms", {}).get(template, {})
        if set(xfms) != {"forward", "reverse"}:
            templates.append(template)
        else:
            found_xfms[template] = xfms

    template_buffer.inputs.in1 = list(found_xfms)
    anat2std_buffer.inputs.in1 = [xfm["forward"] for xfm in found_xfms.values()]
    std2anat_buffer.inputs.in1 = [xfm["reverse"] for xfm in found_xfms.values()]

    if templates:
        LOGGER.info(f"Stage 4: Preparing normalization workflow for {templates}")
        register_template_wf = init_register_template_wf(
            sloppy=sloppy,
            omp_nthreads=omp_nthreads,
            templates=templates,
        )
        ds_template_registration_wf = init_ds_template_registration_wf(output_dir=output_dir)

        # fmt:off
        workflow.connect([
            (inputnode, register_template_wf, [('roi', 'inputnode.lesion_mask')]),
            (t1w_buffer, register_template_wf, [('t1w_preproc', 'inputnode.moving_image')]),
            (refined_buffer, register_template_wf, [('t1w_mask', 'inputnode.moving_mask')]),
            (sourcefile_buffer, ds_template_registration_wf, [
                ("source_files", "inputnode.source_files")
            ]),
            (register_template_wf, ds_template_registration_wf, [
                ('outputnode.template', 'inputnode.template'),
                ('outputnode.anat2std_xfm', 'inputnode.anat2std_xfm'),
                ('outputnode.std2anat_xfm', 'inputnode.std2anat_xfm'),
            ]),
            (register_template_wf, template_buffer, [('outputnode.template', 'in2')]),
            (ds_template_registration_wf, std2anat_buffer, [('outputnode.std2anat_xfm', 'in2')]),
            (ds_template_registration_wf, anat2std_buffer, [('outputnode.anat2std_xfm', 'in2')]),
        ])
        # fmt:on
    if found_xfms:
        LOGGER.info(f"Stage 4: Found pre-computed registrations for {found_xfms}")

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

    workflow.__desc__ = desc

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
        name="surface_recon_wf",
        omp_nthreads=omp_nthreads,
        hires=hires,
        precomputed=precomputed,
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
        ]),
    ])
    # fmt:on

    fsnative_xfms = precomputed.get("transforms", {}).get("fsnative")
    if not fsnative_xfms:
        ds_fs_registration_wf = init_ds_fs_registration_wf(output_dir=output_dir)
        # fmt:off
        workflow.connect([
            (sourcefile_buffer, ds_fs_registration_wf, [
                ("source_files", "inputnode.source_files"),
            ]),
            (surface_recon_wf, ds_fs_registration_wf, [
                ('outputnode.fsnative2t1w_xfm', 'inputnode.fsnative2t1w_xfm'),
            ]),
            (ds_fs_registration_wf, outputnode, [
                ('outputnode.fsnative2t1w_xfm', 'fsnative2t1w_xfm'),
            ]),
        ])
        # fmt:on
    elif "reverse" in fsnative_xfms:
        LOGGER.info("Found fsnative-T1w transform - skipping registration")
        outputnode.inputs.fsnative2t1w_xfm = fsnative_xfms["reverse"]
    else:
        raise RuntimeError(
            "Found a T1w-to-fsnative transform without the reverse. Time to handle this."
        )

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

    if t2w and not have_t2w:
        LOGGER.info("Stage 7: Creating T2w template")
        t2w_template_wf = init_anat_template_wf(
            longitudinal=longitudinal,
            omp_nthreads=omp_nthreads,
            num_files=len(t2w),
            contrast="T2w",
            name="t2w_template_wf",
        )
        bbreg = pe.Node(
            fs.BBRegister(
                contrast_type="t2",
                init="coreg",
                dof=6,
                out_lta_file=True,
                args="--gm-proj-abs 2 --wm-proj-abs 1",
            ),
            name="bbreg",
        )
        coreg_xfms = pe.Node(niu.Merge(2), name="merge_xfms", run_without_submitting=True)
        t2wtot1w_xfm = pe.Node(ConcatenateXFMs(), name="t2wtot1w_xfm", run_without_submitting=True)
        t2w_resample = pe.Node(
            ApplyTransforms(
                dimension=3,
                default_value=0,
                float=True,
                interpolation="LanczosWindowedSinc",
            ),
            name="t2w_resample",
        )

        ds_t2w_preproc = pe.Node(
            DerivativesDataSink(base_directory=output_dir, desc="preproc", compress=True),
            name="ds_t2w_preproc",
            run_without_submitting=True,
        )
        ds_t2w_preproc.inputs.SkullStripped = False

        # fmt:off
        workflow.connect([
            (inputnode, t2w_template_wf, [('t2w', 'inputnode.anat_files')]),
            (t2w_template_wf, bbreg, [('outputnode.anat_ref', 'source_file')]),
            (surface_recon_wf, bbreg, [
                ('outputnode.subject_id', 'subject_id'),
                ('outputnode.subjects_dir', 'subjects_dir'),
            ]),
            (bbreg, coreg_xfms, [('out_lta_file', 'in1')]),
            (surface_recon_wf, coreg_xfms, [('outputnode.fsnative2t1w_xfm', 'in2')]),
            (coreg_xfms, t2wtot1w_xfm, [('out', 'in_xfms')]),
            (t2w_template_wf, t2w_resample, [('outputnode.anat_ref', 'input_image')]),
            (brain_extraction_wf, t2w_resample, [
                (('outputnode.bias_corrected', _pop), 'reference_image'),
            ]),
            (t2wtot1w_xfm, t2w_resample, [('out_xfm', 'transforms')]),
            (inputnode, ds_t2w_preproc, [('t2w', 'source_file')]),
            (t2w_resample, ds_t2w_preproc, [('output_image', 'in_file')]),
            (ds_t2w_preproc, outputnode, [('out_file', 't2w_preproc')]),
        ])
        # fmt:on
    elif not t2w:
        LOGGER.info("No T2w images provided - skipping Stage 7")
    else:
        LOGGER.info("Found preprocessed T2w - skipping Stage 7")

    return workflow


def init_anat_template_wf(
    *,
    longitudinal: bool,
    omp_nthreads: int,
    num_files: int,
    contrast: str,
    name: str = "anat_template_wf",
):
    """
    Generate a canonically-oriented, structural average from all input images.

    Workflow Graph
        .. workflow::
            :graph2use: orig
            :simple_form: yes

            from smriprep.workflows.anatomical import init_anat_template_wf
            wf = init_anat_template_wf(
                longitudinal=False, omp_nthreads=1, num_files=1, contrast="T1w"
            )

    Parameters
    ----------
    longitudinal : :obj:`bool`
        Create unbiased structural average, regardless of number of inputs
        (may increase runtime)
    omp_nthreads : :obj:`int`
        Maximum number of threads an individual process may use
    num_files : :obj:`int`
        Number of images
    contrast : :obj:`str`
        Name of contrast, for reporting purposes, e.g., T1w, T2w, PDw
    name : :obj:`str`, optional
        Workflow name (default: anat_template_wf)

    Inputs
    ------
    anat_files
        List of structural images

    Outputs
    -------
    anat_ref
        Structural reference averaging input images
    anat_valid_list
        List of structural images accepted for combination
    anat_realign_xfm
        List of affine transforms to realign input images to final reference
    out_report
        Conformation report

    """
    workflow = Workflow(name=name)

    if num_files > 1:
        fs_ver = fs.Info().looseversion() or "(version unknown)"
        workflow.__desc__ = f"""\
An anatomical {contrast}-reference map was computed after registration of
{num_files} {contrast} images (after INU-correction) using
`mri_robust_template` [FreeSurfer {fs_ver}, @fs_template].
"""

    inputnode = pe.Node(niu.IdentityInterface(fields=["anat_files"]), name="inputnode")
    outputnode = pe.Node(
        niu.IdentityInterface(
            fields=["anat_ref", "anat_valid_list", "anat_realign_xfm", "out_report"]
        ),
        name="outputnode",
    )

    # 0. Denoise and reorient T1w image(s) to RAS and resample to common voxel space
    anat_ref_dimensions = pe.Node(TemplateDimensions(), name="anat_ref_dimensions")
    denoise = pe.MapNode(
        DenoiseImage(noise_model="Rician", num_threads=omp_nthreads),
        iterfield="input_image",
        name="denoise",
    )
    anat_conform = pe.MapNode(Conform(), iterfield="in_file", name="anat_conform")

    # fmt:off
    workflow.connect([
        (inputnode, anat_ref_dimensions, [('anat_files', 't1w_list')]),
        (anat_ref_dimensions, denoise, [('t1w_valid_list', 'input_image')]),
        (anat_ref_dimensions, anat_conform, [
            ('target_zooms', 'target_zooms'),
            ('target_shape', 'target_shape'),
        ]),
        (denoise, anat_conform, [('output_image', 'in_file')]),
        (anat_ref_dimensions, outputnode, [
            ('out_report', 'out_report'),
            ('t1w_valid_list', 'anat_valid_list'),
        ]),
    ])
    # fmt:on

    if num_files == 1:
        get1st = pe.Node(niu.Select(index=[0]), name="get1st")
        outputnode.inputs.anat_realign_xfm = [pkgr("smriprep", "data/itkIdentityTransform.txt")]

        # fmt:off
        workflow.connect([
            (anat_conform, get1st, [('out_file', 'inlist')]),
            (get1st, outputnode, [('out', 'anat_ref')]),
        ])
        # fmt:on
        return workflow

    anat_conform_xfm = pe.MapNode(
        LTAConvert(in_lta="identity.nofile", out_lta=True),
        iterfield=["source_file", "target_file"],
        name="anat_conform_xfm",
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
    anat_merge = pe.Node(
        StructuralReference(
            auto_detect_sensitivity=True,
            initial_timepoint=1,  # For deterministic behavior
            intensity_scaling=True,  # 7-DOF (rigid + intensity)
            subsample_threshold=200,
            fixed_timepoint=not longitudinal,
            no_iteration=not longitudinal,
            transform_outputs=True,
        ),
        mem_gb=2 * num_files - 1,
        name="anat_merge",
    )

    # 2. Reorient template to RAS, if needed (mri_robust_template may set to LIA)
    anat_reorient = pe.Node(image.Reorient(), name="anat_reorient")

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
        (anat_ref_dimensions, anat_conform_xfm, [('t1w_valid_list', 'source_file')]),
        (anat_conform, anat_conform_xfm, [('out_file', 'target_file')]),
        (anat_conform, n4_correct, [('out_file', 'input_image')]),
        (anat_conform, anat_merge, [
            (('out_file', _set_threads, omp_nthreads), 'num_threads'),
            (('out_file', add_suffix, '_template'), 'out_file')]),
        (n4_correct, anat_merge, [('output_image', 'in_files')]),
        (anat_merge, anat_reorient, [('out_file', 'in_file')]),
        # Combine orientation and template transforms
        (anat_conform_xfm, merge_xfm, [('out_lta', 'in1')]),
        (anat_merge, merge_xfm, [('transform_outputs', 'in2')]),
        (merge_xfm, concat_xfms, [('out', 'in_xfms')]),
        # Output
        (anat_reorient, outputnode, [('out_file', 'anat_ref')]),
        (concat_xfms, outputnode, [('out_xfm', 'anat_realign_xfm')]),
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

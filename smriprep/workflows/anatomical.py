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
from niworkflows.interfaces.nitransforms import ConcatenateXFMs
from niworkflows.interfaces.utility import KeySelect
from niworkflows.utils.misc import fix_multi_T1w_source_name, add_suffix
from niworkflows.anat.ants import init_brain_extraction_wf, init_n4_only_wf
from ..utils.bids import get_outputnode_spec
from ..utils.misc import apply_lut as _apply_bids_lut, fs_isRunning as _fs_isRunning
from .norm import init_anat_norm_wf
from .outputs import init_anat_reports_wf, init_anat_derivatives_wf
from .surfaces import init_surface_recon_wf

LOGGER = logging.getLogger("nipype.workflow")


def init_anat_preproc_wf(
    *,
    bids_root,
    freesurfer,
    hires,
    longitudinal,
    t1w,
    omp_nthreads,
    output_dir,
    skull_strip_mode,
    skull_strip_template,
    spaces,
    debug=False,
    existing_derivatives=None,
    name="anat_preproc_wf",
    skull_strip_fixed_seed=False,
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
            from smriprep.workflows.anatomical import init_anat_preproc_wf
            wf = init_anat_preproc_wf(
                bids_root='.',
                freesurfer=True,
                hires=True,
                longitudinal=False,
                t1w=['t1w.nii.gz'],
                omp_nthreads=1,
                output_dir='.',
                skull_strip_mode='force',
                skull_strip_template=Reference('OASIS30ANTs'),
                spaces=SpatialReferences(spaces=['MNI152NLin2009cAsym', 'fsaverage5']),
            )


    Parameters
    ----------
    bids_root : :obj:`str`
        Path of the input BIDS dataset root
    existing_derivatives : :obj:`dict` or None
        Dictionary mapping output specification attribute names and
        paths to corresponding derivatives.
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
    omp_nthreads : :obj:`int`
        Maximum number of threads an individual process may use
    output_dir : :obj:`str`
        Directory in which to save derivatives
    skull_strip_template : :py:class:`~niworkflows.utils.spaces.Reference`
        Spatial reference to use in atlas-based brain extraction.
    spaces : :py:class:`~niworkflows.utils.spaces.SpatialReferences`
        Object containing standard and nonstandard space specifications.
    debug : :obj:`bool`
        Enable debugging outputs
    name : :obj:`str`, optional
        Workflow name (default: anat_preproc_wf)
    skull_strip_mode : :obj:`str`
        Determiner for T1-weighted skull stripping (`force` ensures skull stripping,
        `skip` ignores skull stripping, and `auto` automatically ignores skull stripping
        if pre-stripped brains are detected).
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
    t1w_brain
        Skull-stripped ``t1w_preproc``
    t1w_mask
        Brain (binary) mask estimated by brain extraction.
    t1w_dseg
        Brain tissue segmentation of the preprocessed structural image, including
        gray-matter (GM), white-matter (WM) and cerebrospinal fluid (CSF).
    t1w_tpms
        List of tissue probability maps corresponding to ``t1w_dseg``.
    std_preproc
        T1w reference resampled in one or more standard spaces.
    std_mask
        Mask of skull-stripped template, in MNI space
    std_dseg
        Segmentation, resampled into MNI space
    std_tpms
        List of tissue probability maps in MNI space
    subjects_dir
        FreeSurfer SUBJECTS_DIR
    anat2std_xfm
        Nonlinear spatial transform to resample imaging data given in anatomical space
        into standard space.
    std2anat_xfm
        Inverse transform of the above.
    subject_id
        FreeSurfer subject ID
    t1w2fsnative_xfm
        LTA-style affine matrix translating from T1w to
        FreeSurfer-conformed subject space
    fsnative2t1w_xfm
        LTA-style affine matrix translating from FreeSurfer-conformed
        subject space to T1w
    surfaces
        GIFTI surfaces (gray/white boundary, midthickness, pial, inflated)

    See Also
    --------
    * :py:func:`~niworkflows.anat.ants.init_brain_extraction_wf`
    * :py:func:`~smriprep.workflows.surfaces.init_surface_recon_wf`

    """
    workflow = Workflow(name=name)
    num_t1w = len(t1w)
    desc = """
Anatomical data preprocessing

: """
    desc += """\
A total of {num_t1w} T1-weighted (T1w) images were found within the input
BIDS dataset.""".format(
        num_t1w=num_t1w
    )

    inputnode = pe.Node(
        niu.IdentityInterface(
            fields=["t1w", "t2w", "roi", "flair", "subjects_dir", "subject_id"]
        ),
        name="inputnode",
    )

    outputnode = pe.Node(
        niu.IdentityInterface(
            fields=["template", "subjects_dir", "subject_id"] + get_outputnode_spec()
        ),
        name="outputnode",
    )

    # Connect reportlets workflows
    anat_reports_wf = init_anat_reports_wf(
        freesurfer=freesurfer,
        output_dir=output_dir,
    )
    # fmt:off
    workflow.connect([
        (outputnode, anat_reports_wf, [
            ('t1w_preproc', 'inputnode.t1w_preproc'),
            ('t1w_mask', 'inputnode.t1w_mask'),
            ('t1w_dseg', 'inputnode.t1w_dseg')]),
    ])
    # fmt:on

    if existing_derivatives is not None:
        LOGGER.log(
            25,
            "Anatomical workflow will reuse prior derivatives found in the "
            "output folder (%s).",
            output_dir,
        )
        desc += """
Anatomical preprocessing was reused from previously existing derivative objects.\n"""
        workflow.__desc__ = desc

        templates = existing_derivatives.pop("template")
        templatesource = pe.Node(
            niu.IdentityInterface(fields=["template"]), name="templatesource"
        )
        templatesource.iterables = [("template", templates)]
        outputnode.inputs.template = templates

        for field, value in existing_derivatives.items():
            setattr(outputnode.inputs, field, value)

        anat_reports_wf.inputs.inputnode.source_file = [
            existing_derivatives["t1w_preproc"]
        ]

        stdselect = pe.Node(
            KeySelect(fields=["std_preproc", "std_mask"], keys=templates),
            name="stdselect",
            run_without_submitting=True,
        )
        # fmt:off
        workflow.connect([
            (inputnode, outputnode, [('subjects_dir', 'subjects_dir'),
                                     ('subject_id', 'subject_id')]),
            (inputnode, anat_reports_wf, [
                ('subjects_dir', 'inputnode.subjects_dir'),
                ('subject_id', 'inputnode.subject_id')]),
            (templatesource, stdselect, [('template', 'key')]),
            (outputnode, stdselect, [('std_preproc', 'std_preproc'),
                                     ('std_mask', 'std_mask')]),
            (stdselect, anat_reports_wf, [
                ('key', 'inputnode.template'),
                ('std_preproc', 'inputnode.std_t1w'),
                ('std_mask', 'inputnode.std_mask'),
            ]),
        ])
        # fmt:on
        return workflow

    # The workflow is not cached.
    desc += (
        """
All of them were corrected for intensity non-uniformity (INU)
"""
        if num_t1w > 1
        else """\
The T1-weighted (T1w) image was corrected for intensity non-uniformity (INU)
"""
    )
    desc += """\
with `N4BiasFieldCorrection` [@n4], distributed with ANTs {ants_ver} \
[@ants, RRID:SCR_004757]"""
    desc += (
        ".\n"
        if num_t1w > 1
        else ", and used as T1w-reference throughout the workflow.\n"
    )

    desc += """\
The T1w-reference was then skull-stripped with a *Nipype* implementation of
the `antsBrainExtraction.sh` workflow (from ANTs), using {skullstrip_tpl}
as target template.
Brain tissue segmentation of cerebrospinal fluid (CSF),
white-matter (WM) and gray-matter (GM) was performed on
the brain-extracted T1w using `fast` [FSL {fsl_ver}, RRID:SCR_002823,
@fsl_fast].
"""

    workflow.__desc__ = desc.format(
        ants_ver=ANTsInfo.version() or "(version unknown)",
        fsl_ver=fsl.FAST().version or "(version unknown)",
        num_t1w=num_t1w,
        skullstrip_tpl=skull_strip_template.fullname,
    )

    buffernode = pe.Node(
        niu.IdentityInterface(fields=["t1w_brain", "t1w_mask"]), name="buffernode"
    )

    # 1. Anatomical reference generation - average input T1w images.
    anat_template_wf = init_anat_template_wf(
        longitudinal=longitudinal, omp_nthreads=omp_nthreads, num_t1w=num_t1w
    )

    anat_validate = pe.Node(
        ValidateImage(), name="anat_validate", run_without_submitting=True
    )

    # 2. Brain-extraction and INU (bias field) correction.
    if skull_strip_mode == "auto":
        import numpy as np
        import nibabel as nb

        def _is_skull_stripped(imgs):
            """Check if T1w images are skull-stripped."""

            def _check_img(img):
                data = np.abs(nb.load(img).get_fdata(dtype=np.float32))
                sidevals = (
                    data[0, :, :].sum()
                    + data[-1, :, :].sum()
                    + data[:, 0, :].sum()
                    + data[:, -1, :].sum()
                    + data[:, :, 0].sum()
                    + data[:, :, -1].sum()
                )
                return sidevals < 10

            return all(_check_img(img) for img in imgs)

        skull_strip_mode = _is_skull_stripped(t1w)

    if skull_strip_mode in (True, "skip"):
        brain_extraction_wf = init_n4_only_wf(
            omp_nthreads=omp_nthreads,
            atropos_use_random_seed=not skull_strip_fixed_seed,
        )
    else:
        brain_extraction_wf = init_brain_extraction_wf(
            in_template=skull_strip_template.space,
            template_spec=skull_strip_template.spec,
            atropos_use_random_seed=not skull_strip_fixed_seed,
            omp_nthreads=omp_nthreads,
            normalization_quality="precise" if not debug else "testing",
        )

    # 4. Spatial normalization
    anat_norm_wf = init_anat_norm_wf(
        debug=debug,
        omp_nthreads=omp_nthreads,
        templates=spaces.get_spaces(nonstandard=False, dim=(3,)),
    )

    # fmt:off
    workflow.connect([
        # Step 1.
        (inputnode, anat_template_wf, [('t1w', 'inputnode.t1w')]),
        (anat_template_wf, anat_validate, [
            ('outputnode.t1w_ref', 'in_file')]),
        (anat_validate, brain_extraction_wf, [
            ('out_file', 'inputnode.in_files')]),
        (brain_extraction_wf, outputnode, [
            (('outputnode.bias_corrected', _pop), 't1w_preproc')]),
        (anat_template_wf, outputnode, [
            ('outputnode.t1w_realign_xfm', 't1w_ref_xfms')]),
        (buffernode, outputnode, [('t1w_brain', 't1w_brain'),
                                  ('t1w_mask', 't1w_mask')]),
        # Steps 2, 3 and 4
        (inputnode, anat_norm_wf, [
            (('t1w', fix_multi_T1w_source_name), 'inputnode.orig_t1w'),
            ('roi', 'inputnode.lesion_mask')]),
        (brain_extraction_wf, anat_norm_wf, [
            (('outputnode.bias_corrected', _pop), 'inputnode.moving_image')]),
        (buffernode, anat_norm_wf, [('t1w_mask', 'inputnode.moving_mask')]),
        (anat_norm_wf, outputnode, [
            ('poutputnode.standardized', 'std_preproc'),
            ('poutputnode.std_mask', 'std_mask'),
            ('poutputnode.std_dseg', 'std_dseg'),
            ('poutputnode.std_tpms', 'std_tpms'),
            ('outputnode.template', 'template'),
            ('outputnode.anat2std_xfm', 'anat2std_xfm'),
            ('outputnode.std2anat_xfm', 'std2anat_xfm'),
        ]),
    ])
    # fmt:on

    # Change LookUp Table - BIDS wants: 0 (bg), 1 (gm), 2 (wm), 3 (csf)
    lut_t1w_dseg = pe.Node(niu.Function(function=_apply_bids_lut), name="lut_t1w_dseg")

    # fmt:off
    workflow.connect([
        (lut_t1w_dseg, anat_norm_wf, [
            ('out', 'inputnode.moving_segmentation')]),
        (lut_t1w_dseg, outputnode, [('out', 't1w_dseg')]),
    ])
    # fmt:on

    # Connect reportlets
    # fmt:off
    workflow.connect([
        (inputnode, anat_reports_wf, [('t1w', 'inputnode.source_file')]),
        (outputnode, anat_reports_wf, [
            ('std_preproc', 'inputnode.std_t1w'),
            ('std_mask', 'inputnode.std_mask'),
        ]),
        (anat_template_wf, anat_reports_wf, [
            ('outputnode.out_report', 'inputnode.t1w_conform_report')]),
        (anat_norm_wf, anat_reports_wf, [
            ('poutputnode.template', 'inputnode.template')]),
    ])
    # fmt:on

    # Write outputs ############################################3
    anat_derivatives_wf = init_anat_derivatives_wf(
        bids_root=bids_root,
        freesurfer=freesurfer,
        num_t1w=num_t1w,
        output_dir=output_dir,
        spaces=spaces,
    )

    # fmt:off
    workflow.connect([
        # Connect derivatives
        (anat_template_wf, anat_derivatives_wf, [
            ('outputnode.t1w_valid_list', 'inputnode.source_files')]),
        (anat_norm_wf, anat_derivatives_wf, [
            ('outputnode.template', 'inputnode.template'),
            ('outputnode.anat2std_xfm', 'inputnode.anat2std_xfm'),
            ('outputnode.std2anat_xfm', 'inputnode.std2anat_xfm')
        ]),
        (outputnode, anat_derivatives_wf, [
            ('t1w_ref_xfms', 'inputnode.t1w_ref_xfms'),
            ('t1w_preproc', 'inputnode.t1w_preproc'),
            ('t1w_mask', 'inputnode.t1w_mask'),
            ('t1w_dseg', 'inputnode.t1w_dseg'),
            ('t1w_tpms', 'inputnode.t1w_tpms'),
        ]),
    ])
    # fmt:on

    # XXX Keeping FAST separate so that it's easier to swap in ANTs or FreeSurfer

    # Brain tissue segmentation - FAST produces: 0 (bg), 1 (wm), 2 (csf), 3 (gm)
    t1w_dseg = pe.Node(
        fsl.FAST(segments=True, no_bias=True, probability_maps=True),
        name="t1w_dseg",
        mem_gb=3,
    )
    lut_t1w_dseg.inputs.lut = (0, 3, 1, 2)  # Maps: 0 -> 0, 3 -> 1, 1 -> 2, 2 -> 3.
    fast2bids = pe.Node(
        niu.Function(function=_probseg_fast2bids),
        name="fast2bids",
        run_without_submitting=True,
    )

    # fmt:off
    workflow.connect([
        (buffernode, t1w_dseg, [('t1w_brain', 'in_files')]),
        (t1w_dseg, lut_t1w_dseg, [('partial_volume_map', 'in_dseg')]),
        (t1w_dseg, fast2bids, [('partial_volume_files', 'inlist')]),
        (fast2bids, anat_norm_wf, [('out', 'inputnode.moving_tpms')]),
        (fast2bids, outputnode, [('out', 't1w_tpms')]),
    ])
    # fmt:on
    if not freesurfer:  # Flag --fs-no-reconall is set - return
        # fmt:off
        workflow.connect([
            (brain_extraction_wf, buffernode, [
                (('outputnode.out_file', _pop), 't1w_brain'),
                ('outputnode.out_mask', 't1w_mask')]),
        ])
        return workflow

    # check for older IsRunning files and remove accordingly
    fs_isrunning = pe.Node(
        niu.Function(function=_fs_isRunning), overwrite=True, name="fs_isrunning"
    )
    fs_isrunning.inputs.logger = LOGGER

    # 5. Surface reconstruction (--fs-no-reconall not set)
    surface_recon_wf = init_surface_recon_wf(
        name="surface_recon_wf", omp_nthreads=omp_nthreads, hires=hires
    )
    applyrefined = pe.Node(fsl.ApplyMask(), name="applyrefined")
    # fmt:off
    workflow.connect([
        (inputnode, fs_isrunning, [
            ('subjects_dir', 'subjects_dir'),
            ('subject_id', 'subject_id')]),
        (inputnode, surface_recon_wf, [
            ('t2w', 'inputnode.t2w'),
            ('flair', 'inputnode.flair'),
            ('subject_id', 'inputnode.subject_id')]),
        (fs_isrunning, surface_recon_wf, [('out', 'inputnode.subjects_dir')]),
        (anat_validate, surface_recon_wf, [('out_file', 'inputnode.t1w')]),
        (brain_extraction_wf, surface_recon_wf, [
            (('outputnode.out_file', _pop), 'inputnode.skullstripped_t1'),
            ('outputnode.out_segm', 'inputnode.ants_segs'),
            (('outputnode.bias_corrected', _pop), 'inputnode.corrected_t1')]),
        (brain_extraction_wf, applyrefined, [
            (('outputnode.bias_corrected', _pop), 'in_file')]),
        (surface_recon_wf, applyrefined, [
            ('outputnode.out_brainmask', 'mask_file')]),
        (surface_recon_wf, outputnode, [
            ('outputnode.subjects_dir', 'subjects_dir'),
            ('outputnode.subject_id', 'subject_id'),
            ('outputnode.t1w2fsnative_xfm', 't1w2fsnative_xfm'),
            ('outputnode.fsnative2t1w_xfm', 'fsnative2t1w_xfm'),
            ('outputnode.surfaces', 'surfaces'),
            ('outputnode.out_aseg', 't1w_aseg'),
            ('outputnode.out_aparc', 't1w_aparc')]),
        (applyrefined, buffernode, [('out_file', 't1w_brain')]),
        (surface_recon_wf, buffernode, [
            ('outputnode.out_brainmask', 't1w_mask')]),
        (surface_recon_wf, anat_reports_wf, [
            ('outputnode.subject_id', 'inputnode.subject_id'),
            ('outputnode.subjects_dir', 'inputnode.subjects_dir')]),
        (surface_recon_wf, anat_derivatives_wf, [
            ('outputnode.out_aseg', 'inputnode.t1w_fs_aseg'),
            ('outputnode.out_aparc', 'inputnode.t1w_fs_aparc'),
        ]),
        (outputnode, anat_derivatives_wf, [
            ('t1w2fsnative_xfm', 'inputnode.t1w2fsnative_xfm'),
            ('fsnative2t1w_xfm', 'inputnode.fsnative2t1w_xfm'),
            ('surfaces', 'inputnode.surfaces'),
        ]),
    ])
    # fmt:on

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

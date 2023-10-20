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
"""
Surface preprocessing workflows.

**sMRIPrep** uses FreeSurfer to reconstruct surfaces from T1w/T2w
structural images.

"""
import typing as ty
from nipype.pipeline import engine as pe
from nipype.interfaces.base import Undefined
from nipype.interfaces import (
    io as nio,
    utility as niu,
    freesurfer as fs,
    workbench as wb,
)

from smriprep.interfaces.surf import MakeRibbon

from ..data import load_resource
from ..interfaces.freesurfer import ReconAll, MakeMidthickness

from niworkflows.engine.workflows import LiterateWorkflow as Workflow
from niworkflows.interfaces.freesurfer import (
    FSDetectInputs,
    FSInjectBrainExtracted,
    PatchedRobustRegister as RobustRegister,
    RefineBrainMask,
)
from niworkflows.interfaces.nitransforms import ConcatenateXFMs
import templateflow.api as tf
from ..interfaces.workbench import CreateSignedDistanceVolume


def init_surface_recon_wf(
    *,
    omp_nthreads: int,
    hires: bool,
    fs_reuse_base: bool,
    precomputed: dict,
    name="surface_recon_wf",
):
    r"""
    Reconstruct anatomical surfaces using FreeSurfer's ``recon-all``.

    Reconstruction is performed in three phases.
    The first phase initializes the subject with T1w and T2w (if available)
    structural images and performs basic reconstruction (``autorecon1``) with the
    exception of skull-stripping.
    For example, a subject with only one session with T1w and T2w images
    would be processed by the following command::

        $ recon-all -sd <output dir>/freesurfer -subjid sub-<subject_label> \
            -i <bids-root>/sub-<subject_label>/anat/sub-<subject_label>_T1w.nii.gz \
            -T2 <bids-root>/sub-<subject_label>/anat/sub-<subject_label>_T2w.nii.gz \
            -autorecon1 \
            -noskullstrip -noT2pial -noFLAIRpial

    The second phase imports an externally computed skull-stripping mask.
    This workflow refines the external brainmask using the internal mask
    implicit the the FreeSurfer's ``aseg.mgz`` segmentation,
    to reconcile ANTs' and FreeSurfer's brain masks.

    First, the ``aseg.mgz`` mask from FreeSurfer is refined in two
    steps, using binary morphological operations:

      1. With a binary closing operation the sulci are included
         into the mask. This results in a smoother brain mask
         that does not exclude deep, wide sulci.

      2. Fill any holes (typically, there could be a hole next to
         the pineal gland and the corpora quadrigemina if the great
         cerebral brain is segmented out).

    Second, the brain mask is grown, including pixels that have a high likelihood
    to the GM tissue distribution:

      3. Dilate and subtract the brain mask, defining the region to search for candidate
         pixels that likely belong to cortical GM.

      4. Pixels found in the search region that are labeled as GM by ANTs
         (during ``antsBrainExtraction.sh``) are directly added to the new mask.

      5. Otherwise, estimate GM tissue parameters locally in  patches of ``ww`` size,
         and test the likelihood of the pixel to belong in the GM distribution.

    This procedure is inspired on mindboggle's solution to the problem:
    https://github.com/nipy/mindboggle/blob/7f91faaa7664d820fe12ccc52ebaf21d679795e2/mindboggle/guts/segment.py#L1660

    The final phase resumes reconstruction, using the T2w image to assist
    in finding the pial surface, if available.
    See :py:func:`~smriprep.workflows.surfaces.init_autorecon_resume_wf` for details.

    Memory annotations for FreeSurfer are based off `their documentation
    <https://surfer.nmr.mgh.harvard.edu/fswiki/SystemRequirements>`_.
    They specify an allocation of 4GB per subject. Here we define 5GB
    to have a certain margin.

    Workflow Graph
        .. workflow::
            :graph2use: orig
            :simple_form: yes

            from smriprep.workflows.surfaces import init_surface_recon_wf
            wf = init_surface_recon_wf(omp_nthreads=1, hires=True, precomputed={})

    Parameters
    ----------
    omp_nthreads : int
        Maximum number of threads an individual process may use
    hires : bool
        Enable sub-millimeter preprocessing in FreeSurfer
    fs_reuse_base : bool
        Adjust pipeline to reuse base template
        of an existing longitudinal freesurfer output

    Inputs
    ------
    t1w
        List of T1-weighted structural images
    t2w
        List of T2-weighted structural images (only first used)
    flair
        List of FLAIR images
    skullstripped_t1
        Skull-stripped T1-weighted image (or mask of image)
    subjects_dir
        FreeSurfer SUBJECTS_DIR
    subject_id
        FreeSurfer subject ID

    Outputs
    -------
    subjects_dir
        FreeSurfer SUBJECTS_DIR
    subject_id
        FreeSurfer subject ID
    fsnative2t1w_xfm
        LTA-style affine matrix translating from FreeSurfer-conformed subject space to T1w

    See also
    --------
    * :py:func:`~smriprep.workflows.surfaces.init_autorecon_resume_wf`

    """
    workflow = Workflow(name=name)
    workflow.__desc__ = """\
Brain surfaces were reconstructed using `recon-all` [FreeSurfer {fs_ver},
RRID:SCR_001847, @fs_reconall], and the brain mask estimated
previously was refined with a custom variation of the method to reconcile
ANTs-derived and FreeSurfer-derived segmentations of the cortical
gray-matter of Mindboggle [RRID:SCR_002438, @mindboggle].
""".format(
        fs_ver=fs.Info().looseversion() or "<ver>"
    )

    inputnode = pe.Node(
        niu.IdentityInterface(
            fields=[
                "t1w",
                "t2w",
                "flair",
                "skullstripped_t1",
                "subjects_dir",
                "subject_id",
            ]
        ),
        name="inputnode",
    )
    outputnode = pe.Node(
        niu.IdentityInterface(
            fields=[
                "subjects_dir",
                "subject_id",
                "t1w2fsnative_xfm",
                "fsnative2t1w_xfm",
            ]
        ),
        name="outputnode",
    )

    recon_config = pe.Node(FSDetectInputs(hires_enabled=hires), name="recon_config")

    fov_check = pe.Node(niu.Function(function=_check_cw256), name="fov_check")
    fov_check.inputs.default_flags = ['-noskullstrip', '-noT2pial', '-noFLAIRpial']

    autorecon1 = pe.Node(
        ReconAll(directive="autorecon1", openmp=omp_nthreads),
        name="autorecon1",
        n_procs=omp_nthreads,
        mem_gb=5,
    )
    autorecon1.interface._can_resume = False
    autorecon1.interface._always_run = True

    skull_strip_extern = pe.Node(FSInjectBrainExtracted(), name="skull_strip_extern")

    autorecon_resume_wf = init_autorecon_resume_wf(omp_nthreads=omp_nthreads)

    get_surfaces = pe.Node(nio.FreeSurferSource(), name="get_surfaces")

    midthickness = pe.MapNode(
        MakeMidthickness(thickness=True, distance=0.5, out_name="midthickness"),
        iterfield="in_file",
        name="midthickness",
    )

    save_midthickness = pe.Node(nio.DataSink(parameterization=False), name="save_midthickness")

    sync = pe.Node(
        niu.Function(
            function=_extract_fs_fields,
            output_names=['subjects_dir', 'subject_id'],
        ),
        name="sync",
    )

    if not fs_reuse_base:

        recon_config = pe.Node(FSDetectInputs(hires_enabled=hires), name="recon_config")

        fov_check = pe.Node(niu.Function(function=_check_cw256), name="fov_check")
        fov_check.inputs.default_flags = ['-noskullstrip', '-noT2pial', '-noFLAIRpial']

        autorecon1 = pe.Node(
            ReconAll(directive="autorecon1", openmp=omp_nthreads),
            name="autorecon1",
            n_procs=omp_nthreads,
            mem_gb=5,
        )
        autorecon1.interface._can_resume = False
        autorecon1.interface._always_run = True

        skull_strip_extern = pe.Node(FSInjectBrainExtracted(), name="skull_strip_extern")

        autorecon_resume_wf = init_autorecon_resume_wf(omp_nthreads=omp_nthreads)

        # fmt:off
        workflow.connect([
            # Configuration
            (inputnode, recon_config, [('t1w', 't1w_list'),
                                       ('t2w', 't2w_list'),
                                       ('flair', 'flair_list')]),
            # Passing subjects_dir / subject_id enforces serial order
            (inputnode, autorecon1, [('subjects_dir', 'subjects_dir'),
                                     ('subject_id', 'subject_id')]),
            (autorecon1, skull_strip_extern, [('subjects_dir', 'subjects_dir'),
                                              ('subject_id', 'subject_id')]),
            (skull_strip_extern, autorecon_resume_wf, [('subjects_dir', 'inputnode.subjects_dir'),
                                                       ('subject_id', 'inputnode.subject_id')]),
            # Reconstruction phases
            (inputnode, autorecon1, [('t1w', 'T1_files')]),
            (inputnode, fov_check, [('t1w', 'in_files')]),
            (fov_check, autorecon1, [('out', 'flags')]),
            (recon_config, autorecon1, [('t2w', 'T2_file'),
                                        ('flair', 'FLAIR_file'),
                                        ('hires', 'hires'),
                                        # First run only (recon-all saves expert options)
                                        ('mris_inflate', 'mris_inflate')]),
            (inputnode, skull_strip_extern, [('skullstripped_t1', 'in_brain')]),
            (recon_config, autorecon_resume_wf, [('use_t2w', 'inputnode.use_T2'),
                                                 ('use_flair', 'inputnode.use_FLAIR')]),
            # Generate mid-thickness surfaces
            (autorecon_resume_wf, get_surfaces, [
                ('outputnode.subjects_dir', 'subjects_dir'),
                ('outputnode.subject_id', 'subject_id'),
            ]),
            (autorecon_resume_wf, save_midthickness, [
                ('outputnode.subjects_dir', 'base_directory'),
                ('outputnode.subject_id', 'container'),
            ]),
        ])
        # fmt:on
    else:
        fs_base_inputs = autorecon1 = pe.Node(
            nio.FreeSurferSource(),
            name='fs_base_inputs'
        )

        # fmt:off
        workflow.connect([
            (inputnode, fs_base_inputs, [('subjects_dir', 'subjects_dir'),
                                         ('subject_id', 'subject_id')]),
            # Generate mid-thickness surfaces
            (inputnode, get_surfaces, [
                ('subjects_dir', 'subjects_dir'),
                ('subject_id', 'subject_id'),
            ]),
            (inputnode, save_midthickness, [
                ('subjects_dir', 'base_directory'),
                ('subject_id', 'container'),
            ]),
        ])
        # fmt:on

    # fmt:off
    workflow.connect([
        (get_surfaces, midthickness, [
            ('white', 'in_file'),
            ('graymid', 'graymid'),
        ]),
        (midthickness, save_midthickness, [('out_file', 'surf.@graymid')]),
        # Output
        (save_midthickness, sync, [('out_file', 'filenames')]),
        (sync, outputnode, [('subjects_dir', 'subjects_dir'),
                            ('subject_id', 'subject_id')]),
    ])
    # fmt:on

    if "fsnative" not in precomputed.get("transforms", {}):
        fsnative2t1w_xfm = pe.Node(
            RobustRegister(auto_sens=True, est_int_scale=True), name="fsnative2t1w_xfm"
        )

        # fmt:off
        workflow.connect([
            (inputnode, fsnative2t1w_xfm, [('t1w', 'target_file')]),
            (autorecon1, fsnative2t1w_xfm, [('T1', 'source_file')]),
            (fsnative2t1w_xfm, outputnode, [('out_reg_file', 'fsnative2t1w_xfm')]),
        ])
        # fmt:on

    return workflow


def init_refinement_wf(*, name="refinement_wf"):
    r"""
    Refine ANTs brain extraction with FreeSurfer segmentation

    Workflow Graph
        .. workflow::
            :graph2use: orig
            :simple_form: yes

            from smriprep.workflows.surfaces import init_refinement_wf
            wf = init_refinement_wf()

    Inputs
    ------
    subjects_dir
        FreeSurfer SUBJECTS_DIR
    subject_id
        FreeSurfer subject ID
    fsnative2t1w_xfm
        LTA-style affine matrix translating from FreeSurfer-conformed subject space to T1w
    reference_image
        Input
    t2w
        List of T2-weighted structural images (only first used)
    flair
        List of FLAIR images
    skullstripped_t1
        Skull-stripped T1-weighted image (or mask of image)
    ants_segs
        Brain tissue segmentation from ANTS ``antsBrainExtraction.sh``
    corrected_t1
        INU-corrected, merged T1-weighted image
    subjects_dir
        FreeSurfer SUBJECTS_DIR
    subject_id
        FreeSurfer subject ID

    Outputs
    -------
    subjects_dir
        FreeSurfer SUBJECTS_DIR
    subject_id
        FreeSurfer subject ID
    t1w2fsnative_xfm
        LTA-style affine matrix translating from T1w to FreeSurfer-conformed subject space
    fsnative2t1w_xfm
        LTA-style affine matrix translating from FreeSurfer-conformed subject space to T1w
    out_brainmask
        Refined brainmask, derived from FreeSurfer's ``aseg`` volume

    See also
    --------
    * :py:func:`~smriprep.workflows.surfaces.init_autorecon_resume_wf`

    """
    workflow = Workflow(name=name)
    workflow.__desc__ = """\
Brain surfaces were reconstructed using `recon-all` [FreeSurfer {fs_ver},
RRID:SCR_001847, @fs_reconall], and the brain mask estimated
previously was refined with a custom variation of the method to reconcile
ANTs-derived and FreeSurfer-derived segmentations of the cortical
gray-matter of Mindboggle [RRID:SCR_002438, @mindboggle].
""".format(
        fs_ver=fs.Info().looseversion() or "<ver>"
    )

    inputnode = pe.Node(
        niu.IdentityInterface(
            fields=[
                "reference_image",
                "ants_segs",
                "fsnative2t1w_xfm",
                "subjects_dir",
                "subject_id",
            ]
        ),
        name="inputnode",
    )
    outputnode = pe.Node(
        niu.IdentityInterface(
            fields=[
                "out_brainmask",
            ]
        ),
        name="outputnode",
    )

    aseg_to_native_wf = init_segs_to_native_wf()
    refine = pe.Node(RefineBrainMask(), name="refine")

    # fmt:off
    workflow.connect([
        # Refine ANTs mask, deriving new mask from FS' aseg
        (inputnode, aseg_to_native_wf, [
            ('subjects_dir', 'inputnode.subjects_dir'),
            ('subject_id', 'inputnode.subject_id'),
            ('reference_image', 'inputnode.in_file'),
            ('fsnative2t1w_xfm', 'inputnode.fsnative2t1w_xfm'),
        ]),
        (inputnode, refine, [('reference_image', 'in_anat'),
                             ('ants_segs', 'in_ants')]),
        (aseg_to_native_wf, refine, [('outputnode.out_file', 'in_aseg')]),
        (refine, outputnode, [('out_file', 'out_brainmask')]),
    ])
    # fmt:on

    return workflow


def init_autorecon_resume_wf(*, omp_nthreads, name="autorecon_resume_wf"):
    r"""
    Resume recon-all execution, assuming the `-autorecon1` stage has been completed.

    In order to utilize resources efficiently, this is broken down into seven
    sub-stages; after the first stage, the second and third stages may be run
    simultaneously, and the fifth and sixth stages may be run simultaneously,
    if resources permit; the fourth stage must be run prior to the fifth and
    sixth, and the seventh must be run after::

        $ recon-all -sd <output dir>/freesurfer -subjid sub-<subject_label> \
            -autorecon2-volonly
        $ recon-all -sd <output dir>/freesurfer -subjid sub-<subject_label> \
            -autorecon-hemi lh -T2pial \
            -noparcstats -noparcstats2 -noparcstats3 -nohyporelabel -nobalabels
        $ recon-all -sd <output dir>/freesurfer -subjid sub-<subject_label> \
            -autorecon-hemi rh -T2pial \
            -noparcstats -noparcstats2 -noparcstats3 -nohyporelabel -nobalabels
        $ recon-all -sd <output dir>/freesurfer -subjid sub-<subject_label> \
            -cortribbon
        $ recon-all -sd <output dir>/freesurfer -subjid sub-<subject_label> \
            -autorecon-hemi lh -nohyporelabel
        $ recon-all -sd <output dir>/freesurfer -subjid sub-<subject_label> \
            -autorecon-hemi rh -nohyporelabel
        $ recon-all -sd <output dir>/freesurfer -subjid sub-<subject_label> \
            -autorecon3

    The parcellation statistics steps are excluded from the second and third
    stages, because they require calculation of the cortical ribbon volume
    (the fourth stage).
    Hypointensity relabeling is excluded from hemisphere-specific steps to avoid
    race conditions, as it is a volumetric operation.

    Workflow Graph
        .. workflow::
            :graph2use: orig
            :simple_form: yes

            from smriprep.workflows.surfaces import init_autorecon_resume_wf
            wf = init_autorecon_resume_wf(omp_nthreads=1)

    Inputs
    ------
    subjects_dir
        FreeSurfer SUBJECTS_DIR
    subject_id
        FreeSurfer subject ID
    use_T2
        Refine pial surface using T2w image
    use_FLAIR
        Refine pial surface using FLAIR image

    Outputs
    -------
    subjects_dir
        FreeSurfer SUBJECTS_DIR
    subject_id
        FreeSurfer subject ID

    """
    workflow = Workflow(name=name)

    inputnode = pe.Node(
        niu.IdentityInterface(fields=["subjects_dir", "subject_id", "use_T2", "use_FLAIR"]),
        name="inputnode",
    )

    outputnode = pe.Node(
        niu.IdentityInterface(fields=["subjects_dir", "subject_id"]), name="outputnode"
    )

    # FreeSurfer 7.3 removed gcareg from autorecon2-volonly
    # Adding it directly in would force it to run every time
    gcareg = pe.Node(
        ReconAll(directive=Undefined, steps=["gcareg"], openmp=omp_nthreads),
        n_procs=omp_nthreads,
        mem_gb=5,
        name="gcareg",
    )
    gcareg.interface._always_run = True

    autorecon2_vol = pe.Node(
        ReconAll(directive="autorecon2-volonly", openmp=omp_nthreads),
        n_procs=omp_nthreads,
        mem_gb=5,
        name="autorecon2_vol",
    )
    autorecon2_vol.interface._always_run = True

    autorecon_surfs = pe.MapNode(
        ReconAll(
            directive="autorecon-hemi",
            flags=[
                "-noparcstats",
                "-noparcstats2",
                "-noparcstats3",
                "-nohyporelabel",
                "-nobalabels",
            ],
            openmp=omp_nthreads,
        ),
        iterfield="hemi",
        n_procs=omp_nthreads,
        mem_gb=5,
        name="autorecon_surfs",
    )
    autorecon_surfs.inputs.hemi = ["lh", "rh"]
    autorecon_surfs.interface._always_run = True

    # -cortribbon is a prerequisite for -parcstats, -parcstats2, -parcstats3
    # Claiming two threads because pial refinement can be split by hemisphere
    # if -T2pial or -FLAIRpial is enabled.
    # Parallelizing by hemisphere saves ~30 minutes over simply enabling
    # OpenMP on an 8 core machine.
    cortribbon = pe.Node(
        ReconAll(directive=Undefined, steps=["cortribbon"], parallel=True),
        n_procs=2,
        name="cortribbon",
    )
    cortribbon.interface._always_run = True

    # -parcstats* can be run per-hemisphere
    # -hyporelabel is volumetric, even though it's part of -autorecon-hemi
    parcstats = pe.MapNode(
        ReconAll(directive="autorecon-hemi", flags=["-nohyporelabel"], openmp=omp_nthreads),
        iterfield="hemi",
        n_procs=omp_nthreads,
        mem_gb=5,
        name="parcstats",
    )
    parcstats.inputs.hemi = ["lh", "rh"]
    parcstats.interface._always_run = True

    # Runs: -hyporelabel -aparc2aseg -apas2aseg -segstats -wmparc
    # All volumetric, so don't
    autorecon3 = pe.Node(
        ReconAll(directive="autorecon3", openmp=omp_nthreads),
        n_procs=omp_nthreads,
        mem_gb=5,
        name="autorecon3",
    )
    autorecon3.interface._always_run = True

    def _dedup(in_list):
        vals = set(in_list)
        if len(vals) > 1:
            raise ValueError(f"Non-identical values can't be deduplicated:\n{in_list!r}")
        return vals.pop()

    # fmt:off
    workflow.connect([
        (inputnode, cortribbon, [('use_T2', 'use_T2'),
                                 ('use_FLAIR', 'use_FLAIR')]),
        (inputnode, gcareg, [('subjects_dir', 'subjects_dir'),
                             ('subject_id', 'subject_id')]),
        (gcareg, autorecon2_vol, [('subjects_dir', 'subjects_dir'),
                                  ('subject_id', 'subject_id')]),
        (autorecon2_vol, autorecon_surfs, [('subjects_dir', 'subjects_dir'),
                                           ('subject_id', 'subject_id')]),
        (autorecon_surfs, cortribbon, [(('subjects_dir', _dedup), 'subjects_dir'),
                                       (('subject_id', _dedup), 'subject_id')]),
        (cortribbon, parcstats, [('subjects_dir', 'subjects_dir'),
                                 ('subject_id', 'subject_id')]),
        (parcstats, autorecon3, [(('subjects_dir', _dedup), 'subjects_dir'),
                                 (('subject_id', _dedup), 'subject_id')]),
        (autorecon3, outputnode, [('subjects_dir', 'subjects_dir'),
                                  ('subject_id', 'subject_id')]),
    ])
    # fmt:on

    return workflow


def init_surface_derivatives_wf(
    *,
    cifti_output: ty.Literal["91k", "170k", False] = False,
    name="surface_derivatives_wf",
):
    r"""
    Generate sMRIPrep derivatives from FreeSurfer derivatives

    Workflow Graph
        .. workflow::
            :graph2use: orig
            :simple_form: yes

            from smriprep.workflows.surfaces import init_surface_derivatives_wf
            wf = init_surface_derivatives_wf()

    Inputs
    ------
    reference
        Reference image in native T1w space, for defining a resampling grid
    fsnative2t1w_xfm
        LTA-style affine matrix translating from FreeSurfer-conformed subject space to T1w
    subjects_dir
        FreeSurfer SUBJECTS_DIR
    subject_id
        FreeSurfer subject ID

    Outputs
    -------
    surfaces
        GIFTI surfaces for gray/white matter boundary, pial surface,
        midthickness (or graymid) surface, and inflated surfaces
    morphometrics
        GIFTIs of cortical thickness, curvature, and sulcal depth
    out_aseg
        FreeSurfer's aseg segmentation, in native T1w space
    out_aparc
        FreeSurfer's aparc+aseg segmentation, in native T1w space

    See also
    --------
    * :py:func:`~smriprep.workflows.surfaces.init_gifti_surface_wf`

    """
    workflow = Workflow(name=name)

    inputnode = pe.Node(
        niu.IdentityInterface(
            fields=[
                "subjects_dir",
                "subject_id",
                "fsnative2t1w_xfm",
                "reference",
            ]
        ),
        name="inputnode",
    )
    outputnode = pe.Node(
        niu.IdentityInterface(
            fields=[
                "inflated",
                "curv",
                "out_aseg",
                "out_aparc",
                "cifti_morph",
                "cifti_metadata",
            ]
        ),
        name="outputnode",
    )

    gifti_surfaces_wf = init_gifti_surfaces_wf(surfaces=["inflated"])
    gifti_morph_wf = init_gifti_morphometrics_wf(morphometrics=["curv"])
    aseg_to_native_wf = init_segs_to_native_wf()
    aparc_to_native_wf = init_segs_to_native_wf(segmentation="aparc_aseg")

    # fmt:off
    workflow.connect([
        # Configuration
        (inputnode, gifti_surfaces_wf, [
            ('subjects_dir', 'inputnode.subjects_dir'),
            ('subject_id', 'inputnode.subject_id'),
            ('fsnative2t1w_xfm', 'inputnode.fsnative2t1w_xfm'),
        ]),
        (inputnode, gifti_morph_wf, [
            ('subjects_dir', 'inputnode.subjects_dir'),
            ('subject_id', 'inputnode.subject_id'),
        ]),
        (inputnode, aseg_to_native_wf, [
            ('subjects_dir', 'inputnode.subjects_dir'),
            ('subject_id', 'inputnode.subject_id'),
            ('reference', 'inputnode.in_file'),
            ('fsnative2t1w_xfm', 'inputnode.fsnative2t1w_xfm'),
        ]),
        (inputnode, aparc_to_native_wf, [
            ('subjects_dir', 'inputnode.subjects_dir'),
            ('subject_id', 'inputnode.subject_id'),
            ('reference', 'inputnode.in_file'),
            ('fsnative2t1w_xfm', 'inputnode.fsnative2t1w_xfm'),
        ]),

        # Output
        (gifti_surfaces_wf, outputnode, [('outputnode.inflated', 'inflated')]),
        (aseg_to_native_wf, outputnode, [('outputnode.out_file', 'out_aseg')]),
        (aparc_to_native_wf, outputnode, [('outputnode.out_file', 'out_aparc')]),
        (gifti_morph_wf, outputnode, [('outputnode.curv', 'curv')]),
    ])
    # fmt:on

    if cifti_output:
        morph_grayords_wf = init_morph_grayords_wf(grayord_density=cifti_output)
        # fmt:off
        workflow.connect([
            (inputnode, morph_grayords_wf, [
                ('subject_id', 'inputnode.subject_id'),
                ('subjects_dir', 'inputnode.subjects_dir'),
            ]),
            (morph_grayords_wf, outputnode, [
                ("outputnode.cifti_morph", "cifti_morph"),
                ("outputnode.cifti_metadata", "cifti_metadata"),
            ]),
        ])
        # fmt:on

    return workflow


def init_fsLR_reg_wf(*, name="fsLR_reg_wf"):
    """Generate GIFTI registration files to fsLR space"""
    from ..interfaces.workbench import SurfaceSphereProjectUnproject

    workflow = Workflow(name=name)

    inputnode = pe.Node(niu.IdentityInterface(["sphere_reg", "sulc"]), name="inputnode")
    outputnode = pe.Node(niu.IdentityInterface(["sphere_reg_fsLR"]), name="outputnode")

    # Via
    # ${CARET7DIR}/wb_command -surface-sphere-project-unproject
    #   "$AtlasSpaceFolder"/"$NativeFolder"/"$Subject"."$Hemisphere".sphere.reg.native.surf.gii
    #   "$AtlasSpaceFolder"/fsaverage/"$Subject"."$Hemisphere".sphere."$HighResMesh"k_fs_"$Hemisphere".surf.gii
    #   "$AtlasSpaceFolder"/fsaverage/"$Subject"."$Hemisphere".def_sphere."$HighResMesh"k_fs_"$Hemisphere".surf.gii
    #   "$AtlasSpaceFolder"/"$NativeFolder"/"$Subject"."$Hemisphere".sphere.reg.reg_LR.native.surf.gii
    project_unproject = pe.MapNode(
        SurfaceSphereProjectUnproject(),
        iterfield=["sphere_in", "sphere_project_to", "sphere_unproject_from"],
        name="project_unproject",
    )
    atlases = load_resource('atlases')
    project_unproject.inputs.sphere_project_to = [
        atlases / 'fs_L' / 'fsaverage.L.sphere.164k_fs_L.surf.gii',
        atlases / 'fs_R' / 'fsaverage.R.sphere.164k_fs_R.surf.gii',
    ]
    project_unproject.inputs.sphere_unproject_from = [
        atlases / 'fs_L' / 'fs_L-to-fs_LR_fsaverage.L_LR.spherical_std.164k_fs_L.surf.gii',
        atlases / 'fs_R' / 'fs_R-to-fs_LR_fsaverage.R_LR.spherical_std.164k_fs_R.surf.gii',
    ]

    # fmt:off
    workflow.connect([
        (inputnode, project_unproject, [('sphere_reg', 'sphere_in')]),
        (project_unproject, outputnode, [('sphere_out', 'sphere_reg_fsLR')]),
    ])
    # fmt:on

    return workflow


def init_msm_sulc_wf(*, sloppy: bool = False, name: str = 'msm_sulc_wf'):
    """Run MSMSulc registration to fsLR surfaces, per hemisphere."""
    from ..interfaces.msm import MSM
    from ..interfaces.workbench import (
        SurfaceAffineRegression,
        SurfaceApplyAffine,
        SurfaceModifySphere,
    )

    workflow = Workflow(name=name)
    inputnode = pe.Node(
        niu.IdentityInterface(fields=['sulc', 'sphere', 'sphere_reg_fsLR']),
        name='inputnode',
    )
    outputnode = pe.Node(niu.IdentityInterface(fields=['sphere_reg_fsLR']), name='outputnode')

    # 0) Calculate affine
    # ${CARET7DIR}/wb_command -surface-affine-regression \
    # $SUB.L.sphere.native.surf.gii  \
    # $SUB.sphere.reg.reg_LR.native.surf.gii \
    # "$AtlasSpaceFolder"/"$NativeFolder"/MSMSulc/${Hemisphere}.mat
    regress_affine = pe.MapNode(
        SurfaceAffineRegression(),
        iterfield=['in_surface', 'target_surface'],
        name='regress_affine',
    )

    # 1) Apply affine to native sphere:
    # wb_command -surface-apply-affine \
    # ${SUB}.L.sphere.native.surf.gii \
    # L.mat \
    # ${SUB}.L.sphere_rot.native.surf.gii
    apply_surface_affine = pe.MapNode(
        SurfaceApplyAffine(),
        iterfield=['in_surface', 'in_affine'],
        name='apply_surface_affine',
    )

    # Fix for oblongated sphere
    modify_sphere = pe.MapNode(
        SurfaceModifySphere(radius=100),
        iterfield=['in_surface'],
        name='modify_sphere',
    )

    # 2) Run MSMSulc
    # ./msm_centos_v3 --conf=MSMSulcStrainFinalconf \
    # --inmesh=${SUB}.${HEMI}.sphere_rot.native.surf.gii
    # --refmesh=fsaverage.${HEMI}_LR.spherical_std.164k_fs_LR.surf.gii
    # --indata=sub-${SUB}_ses-${SES}_hemi-${HEMI)_sulc.shape.gii \
    # --refdata=tpl-fsaverage_hemi-${HEMI}_den-164k_sulc.shape.gii \
    # --out=${HEMI}. --verbose
    msm_conf = load_resource(f'msm/MSMSulcStrain{"Sloppy" if sloppy else "Final"}conf')
    msmsulc = pe.MapNode(
        MSM(verbose=True, config_file=msm_conf),
        iterfield=['in_mesh', 'reference_mesh', 'in_data', 'reference_data', 'out_base'],
        name='msmsulc',
        mem_gb=2,
    )
    msmsulc.inputs.out_base = ['lh.', 'rh.']  # To placate Path2BIDS
    msmsulc.inputs.reference_mesh = [
        str(
            tf.get(
                'fsaverage',
                hemi=hemi,
                density='164k',
                desc='std',
                suffix='sphere',
                extension='.surf.gii',
            )
        )
        for hemi in 'LR'
    ]
    msmsulc.inputs.reference_data = [
        str(
            tf.get(
                'fsaverage',
                hemi=hemi,
                density='164k',
                suffix='sulc',
                extension='.shape.gii',
            )
        )
        for hemi in 'LR'
    ]
    # fmt:off
    workflow.connect([
        (inputnode, regress_affine, [('sphere', 'in_surface'),
                                     ('sphere_reg_fsLR', 'target_surface')]),
        (inputnode, apply_surface_affine, [('sphere', 'in_surface')]),
        (regress_affine, apply_surface_affine, [('out_affine', 'in_affine')]),
        (apply_surface_affine, modify_sphere, [('out_surface', 'in_surface')]),
        (inputnode, msmsulc, [('sulc', 'in_data')]),
        (modify_sphere, msmsulc, [('out_surface', 'in_mesh')]),
        (msmsulc, outputnode, [('warped_mesh', 'sphere_reg_fsLR')]),
    ])
    # fmt:on
    return workflow


def init_gifti_surfaces_wf(
    *,
    surfaces: ty.List[str] = ["pial", "midthickness", "inflated", "white"],
    to_scanner: bool = True,
    name: str = "gifti_surface_wf",
):
    r"""
    Prepare GIFTI surfaces from a FreeSurfer subjects directory.

    The default surfaces are ``lh/rh.pial``, ``lh/rh.midthickness``,
    ``lh/rh.inflated``, and ``lh/rh.white``.

    Vertex coordinates are :py:class:`transformed
    <smriprep.interfaces.NormalizeSurf>` to align with native T1w space
    when ``fsnative2t1w_xfm`` is provided.

    Workflow Graph
        .. workflow::
            :graph2use: orig
            :simple_form: yes

            from smriprep.workflows.surfaces import init_gifti_surfaces_wf
            wf = init_gifti_surfaces_wf()

    Inputs
    ------
    subjects_dir
        FreeSurfer SUBJECTS_DIR
    subject_id
        FreeSurfer subject ID
    fsnative2t1w_xfm
        LTA formatted affine transform file

    Outputs
    -------
    surfaces
        GIFTI surfaces for all requested surfaces
    ``<surface>``
        Left and right GIFTIs for each surface passed to ``surfaces``

    """
    from ..interfaces.surf import NormalizeSurf

    workflow = Workflow(name=name)

    inputnode = pe.Node(
        niu.IdentityInterface(["subjects_dir", "subject_id", "fsnative2t1w_xfm"]),
        name="inputnode",
    )
    outputnode = pe.Node(niu.IdentityInterface(["surfaces", *surfaces]), name="outputnode")

    get_surfaces = pe.Node(
        niu.Function(function=_get_surfaces, output_names=surfaces),
        name="get_surfaces",
    )
    get_surfaces.inputs.surfaces = surfaces

    surface_list = pe.Node(
        niu.Merge(len(surfaces), ravel_inputs=True),
        name="surface_list",
        run_without_submitting=True,
    )
    fs2gii = pe.MapNode(
        fs.MRIsConvert(out_datatype="gii", to_scanner=to_scanner),
        iterfield="in_file",
        name="fs2gii",
    )
    fix_surfs = pe.MapNode(NormalizeSurf(), iterfield="in_file", name="fix_surfs")

    surface_groups = pe.Node(
        niu.Split(splits=[2] * len(surfaces)),
        name="surface_groups",
        run_without_submitting=True,
    )

    # fmt:off
    workflow.connect([
        (inputnode, get_surfaces, [('subjects_dir', 'subjects_dir'),
                                   ('subject_id', 'subject_id')]),
        (get_surfaces, surface_list, [
            (surf, f'in{i}') for i, surf in enumerate(surfaces, start=1)
        ]),
        (surface_list, fs2gii, [('out', 'in_file')]),
        (fs2gii, fix_surfs, [('converted', 'in_file')]),
        (fix_surfs, outputnode, [('out_file', 'surfaces')]),
        (fix_surfs, surface_groups, [('out_file', 'inlist')]),
        (surface_groups, outputnode, [
            (f'out{i}', surf) for i, surf in enumerate(surfaces, start=1)
        ]),
    ])
    # fmt:on
    return workflow


def init_gifti_morphometrics_wf(
    *,
    morphometrics: ty.List[str] = ["thickness", "curv", "sulc"],
    name: str = "gifti_morphometrics_wf",
):
    r"""
    Prepare GIFTI shape files from morphometrics found in a FreeSurfer subjects
    directory.

    The default morphometrics are ``lh/rh.thickness``, ``lh/rh.curv``, and
    ``lh/rh.sulc``.

    Workflow Graph
        .. workflow::
            :graph2use: orig
            :simple_form: yes

            from smriprep.workflows.surfaces import init_gifti_morphometrics_wf
            wf = init_gifti_morphometrics_wf()

    Inputs
    ------
    subjects_dir
        FreeSurfer SUBJECTS_DIR
    subject_id
        FreeSurfer subject ID
    fsnative2t1w_xfm
        LTA formatted affine transform file (inverse)

    Outputs
    -------
    morphometrics
        GIFTI shape files for all requested morphometrics
    ``<morphometric>``
        Left and right GIFTIs for each morphometry type passed to ``morphometrics``

    """
    from ..interfaces.freesurfer import MRIsConvertData

    workflow = Workflow(name=name)

    inputnode = pe.Node(
        niu.IdentityInterface(["subjects_dir", "subject_id"]),
        name="inputnode",
    )
    outputnode = pe.Node(
        niu.IdentityInterface(
            [
                "morphometrics",
                *morphometrics,
            ]
        ),
        name="outputnode",
    )

    get_subject = pe.Node(nio.FreeSurferSource(), name="get_surfaces")

    morphometry_list = pe.Node(
        niu.Merge(len(morphometrics), ravel_inputs=True),
        name="surfmorph_list",
        run_without_submitting=True,
    )
    morphs2gii = pe.MapNode(
        MRIsConvertData(out_datatype="gii"),
        iterfield="scalarcurv_file",
        name="morphs2gii",
    )

    morph_groups = pe.Node(
        niu.Split(splits=[2] * len(morphometrics)),
        name="morph_groups",
        run_without_submitting=True,
    )

    # fmt:off
    workflow.connect([
        (inputnode, get_subject, [('subjects_dir', 'subjects_dir'),
                                  ('subject_id', 'subject_id')]),
        (get_subject, morphometry_list, [
            ((morph, _sorted_by_basename), f'in{i}')
            for i, morph in enumerate(morphometrics, start=1)
        ]),
        (morphometry_list, morphs2gii, [('out', 'scalarcurv_file')]),
        (morphs2gii, outputnode, [('converted', 'morphometrics')]),
        # Output individual surfaces as well
        (morphs2gii, morph_groups, [('converted', 'inlist')]),
        (morph_groups, outputnode, [
            (f'out{i}', surf) for i, surf in enumerate(morphometrics, start=1)
        ]),
    ])
    # fmt:on
    return workflow


def init_segs_to_native_wf(*, name="segs_to_native", segmentation="aseg"):
    """
    Get a segmentation from FreeSurfer conformed space into native T1w space.

    Workflow Graph
        .. workflow::
            :graph2use: orig
            :simple_form: yes

            from smriprep.workflows.surfaces import init_segs_to_native_wf
            wf = init_segs_to_native_wf()

    Parameters
    ----------
    segmentation
        The name of a segmentation ('aseg' or 'aparc_aseg' or 'wmparc')

    Inputs
    ------
    in_file
        Anatomical, merged T1w image after INU correction
    subjects_dir
        FreeSurfer SUBJECTS_DIR
    subject_id
        FreeSurfer subject ID
    fsnative2t1w_xfm
        LTA-style affine matrix translating from FreeSurfer-conformed subject space to T1w

    Outputs
    -------
    out_file
        The selected segmentation, after resampling in native space

    """
    workflow = Workflow(name=f"{name}_{segmentation}")
    inputnode = pe.Node(
        niu.IdentityInterface(["in_file", "subjects_dir", "subject_id", "fsnative2t1w_xfm"]),
        name="inputnode",
    )
    outputnode = pe.Node(niu.IdentityInterface(["out_file"]), name="outputnode")
    # Extract the aseg and aparc+aseg outputs
    fssource = pe.Node(nio.FreeSurferSource(), name="fs_datasource")

    lta = pe.Node(ConcatenateXFMs(out_fmt="fs"), name="lta", run_without_submitting=True)

    # Resample from T1.mgz to T1w.nii.gz, applying any offset in fsnative2t1w_xfm,
    # and convert to NIfTI while we're at it
    resample = pe.Node(
        fs.ApplyVolTransform(transformed_file="seg.nii.gz", interp="nearest"),
        name="resample",
    )

    if segmentation.startswith("aparc"):
        if segmentation == "aparc_aseg":

            def _sel(x):
                return [parc for parc in x if "aparc+" in parc][0]  # noqa

        elif segmentation == "aparc_a2009s":

            def _sel(x):
                return [parc for parc in x if "a2009s+" in parc][0]  # noqa

        elif segmentation == "aparc_dkt":

            def _sel(x):
                return [parc for parc in x if "DKTatlas+" in parc][0]  # noqa

        segmentation = (segmentation, _sel)

    # fmt:off
    workflow.connect([
        (inputnode, fssource, [
            ('subjects_dir', 'subjects_dir'),
            ('subject_id', 'subject_id')]),
        (inputnode, lta, [('in_file', 'reference'),
                          ('fsnative2t1w_xfm', 'in_xfms')]),
        (fssource, lta, [('T1', 'moving')]),
        (inputnode, resample, [('in_file', 'target_file')]),
        (fssource, resample, [(segmentation, 'source_file')]),
        (lta, resample, [('out_xfm', 'lta_file')]),
        (resample, outputnode, [('transformed_file', 'out_file')]),
    ])
    # fmt:on
    return workflow


def init_anat_ribbon_wf(name="anat_ribbon_wf"):
    """Create anatomical ribbon mask

    Workflow Graph

        .. workflow::
            :graph2use: orig
            :simple_form: yes

            from smriprep.workflows.surfaces import init_anat_ribbon_wf
            wf = init_anat_ribbon_wf()

    Inputs
    ------
    white
        Left and right gray/white surfaces (as GIFTI files)
    pial
        Left and right pial surfaces (as GIFTI files)
    ref_file
        Reference image (one 3D volume) to define the target space

    Outputs
    -------
    anat_ribbon
        Cortical gray matter mask, sampled into ``ref_file`` space
    """
    DEFAULT_MEMORY_MIN_GB = 0.01
    workflow = pe.Workflow(name=name)

    inputnode = pe.Node(
        niu.IdentityInterface(fields=["white", "pial", "ref_file"]),
        name="inputnode",
    )
    outputnode = pe.Node(niu.IdentityInterface(fields=["anat_ribbon"]), name="outputnode")

    create_wm_distvol = pe.MapNode(
        CreateSignedDistanceVolume(),
        iterfield=["surf_file"],
        name="create_wm_distvol",
    )

    create_pial_distvol = pe.MapNode(
        CreateSignedDistanceVolume(),
        iterfield=["surf_file"],
        name="create_pial_distvol",
    )

    make_ribbon = pe.Node(MakeRibbon(), name="make_ribbon", mem_gb=DEFAULT_MEMORY_MIN_GB)

    # fmt: off
    workflow.connect(
        [
            (inputnode, create_wm_distvol, [
                ("white", "surf_file"),
                ("ref_file", "ref_file"),
            ]),
            (inputnode, create_pial_distvol, [
                ("pial", "surf_file"),
                ("ref_file", "ref_file"),
            ]),
            (create_wm_distvol, make_ribbon, [("out_file", "white_distvols")]),
            (create_pial_distvol, make_ribbon, [("out_file", "pial_distvols")]),
            (make_ribbon, outputnode, [("ribbon", "anat_ribbon")]),
        ]
    )
    # fmt: on
    return workflow


def init_morph_grayords_wf(
    grayord_density: ty.Literal['91k', '170k'],
    name: str = "morph_grayords_wf",
):
    """
    Sample Grayordinates files onto the fsLR atlas.

    Outputs are in CIFTI2 format.

    Workflow Graph
        .. workflow::
            :graph2use: colored
            :simple_form: yes

            from smriprep.workflows.surfaces import init_morph_grayords_wf
            wf = init_morph_grayords_wf(grayord_density="91k")

    Parameters
    ----------
    grayord_density : :obj:`str`
        Either `91k` or `170k`, representing the total of vertices or *grayordinates*.
    name : :obj:`str`
        Unique name for the subworkflow (default: ``"morph_grayords_wf"``)

    Inputs
    ------
    subject_id : :obj:`str`
        FreeSurfer subject ID
    subjects_dir : :obj:`str`
        FreeSurfer SUBJECTS_DIR

    Outputs
    -------
    cifti_morph : :obj:`list` of :obj:`str`
        Paths of CIFTI dscalar files
    cifti_metadata : :obj:`list` of :obj:`str`
        Paths to JSON files containing metadata corresponding to ``cifti_morph``

    """
    import templateflow.api as tf
    from niworkflows.engine.workflows import LiterateWorkflow as Workflow
    from smriprep.interfaces.cifti import GenerateDScalar

    workflow = Workflow(name=name)
    workflow.__desc__ = f"""\
*Grayordinate* "dscalar" files [@hcppipelines] containing {grayord_density} samples were
also generated using the highest-resolution ``fsaverage`` as an intermediate standardized
surface space.
"""

    fslr_density = "32k" if grayord_density == "91k" else "59k"

    inputnode = pe.Node(
        niu.IdentityInterface(fields=["subject_id", "subjects_dir"]),
        name="inputnode",
    )

    outputnode = pe.Node(
        niu.IdentityInterface(fields=["cifti_morph", "cifti_metadata"]),
        name="outputnode",
    )

    get_surfaces = pe.Node(nio.FreeSurferSource(), name="get_surfaces")

    surfmorph_list = pe.Node(
        niu.Merge(3, ravel_inputs=True),
        name="surfmorph_list",
        run_without_submitting=True,
    )

    surf2surf = pe.MapNode(
        fs.SurfaceTransform(target_subject="fsaverage", target_type="gii"),
        iterfield=["source_file", "hemi"],
        name="surf2surf",
        mem_gb=0.01,
    )
    surf2surf.inputs.hemi = ["lh", "rh"] * 3

    # Setup Workbench command. LR ordering for hemi can be assumed, as it is imposed
    # by the iterfield of the MapNode in the surface sampling workflow above.
    resample = pe.MapNode(
        wb.MetricResample(method="ADAP_BARY_AREA", area_metrics=True),
        name="resample",
        iterfield=[
            "in_file",
            "out_file",
            "new_sphere",
            "new_area",
            "current_sphere",
            "current_area",
        ],
    )
    resample.inputs.current_sphere = [
        str(
            tf.get(
                "fsaverage",
                hemi=hemi,
                density="164k",
                desc="std",
                suffix="sphere",
                extension=".surf.gii",
            )
        )
        for hemi in "LR"
    ] * 3
    resample.inputs.current_area = [
        str(
            tf.get(
                "fsaverage",
                hemi=hemi,
                density="164k",
                desc="vaavg",
                suffix="midthickness",
                extension=".shape.gii",
            )
        )
        for hemi in "LR"
    ] * 3
    resample.inputs.new_sphere = [
        str(
            tf.get(
                "fsLR",
                space="fsaverage",
                hemi=hemi,
                density=fslr_density,
                suffix="sphere",
                extension=".surf.gii",
            )
        )
        for hemi in "LR"
    ] * 3
    resample.inputs.new_area = [
        str(
            tf.get(
                "fsLR",
                hemi=hemi,
                density=fslr_density,
                desc="vaavg",
                suffix="midthickness",
                extension=".shape.gii",
            )
        )
        for hemi in "LR"
    ] * 3
    resample.inputs.out_file = [
        f"space-fsLR_hemi-{h}_den-{grayord_density}_{morph}.shape.gii"
        # Order: curv-L, curv-R, sulc-L, sulc-R, thickness-L, thickness-R
        for morph in ('curv', 'sulc', 'thickness')
        for h in "LR"
    ]

    gen_cifti = pe.MapNode(
        GenerateDScalar(
            grayordinates=grayord_density,
        ),
        iterfield=['scalar_name', 'scalar_surfs'],
        name="gen_cifti",
    )
    gen_cifti.inputs.scalar_name = ['curv', 'sulc', 'thickness']

    # fmt: off
    workflow.connect([
        (inputnode, get_surfaces, [
            ('subject_id', 'subject_id'),
            ('subjects_dir', 'subjects_dir'),
        ]),
        (inputnode, surf2surf, [
            ('subject_id', 'source_subject'),
            ('subjects_dir', 'subjects_dir'),
        ]),
        (get_surfaces, surfmorph_list, [
            (('curv', _sorted_by_basename), 'in1'),
            (('sulc', _sorted_by_basename), 'in2'),
            (('thickness', _sorted_by_basename), 'in3'),
        ]),
        (surfmorph_list, surf2surf, [('out', 'source_file')]),
        (surf2surf, resample, [('out_file', 'in_file')]),
        (resample, gen_cifti, [
            (("out_file", _collate), "scalar_surfs")]),
        (gen_cifti, outputnode, [("out_file", "cifti_morph"),
                                 ("out_metadata", "cifti_metadata")]),
    ])
    # fmt: on

    return workflow


def _check_cw256(in_files, default_flags):
    import numpy as np
    from nibabel.funcs import concat_images

    if isinstance(in_files, str):
        in_files = [in_files]
    summary_img = concat_images(in_files)
    fov = np.array(summary_img.shape[:3]) * summary_img.header.get_zooms()[:3]
    flags = list(default_flags)
    if np.any(fov > 256):
        flags.append("-cw256")
    return flags


def _sorted_by_basename(inlist):
    from os.path import basename

    return sorted(inlist, key=lambda x: str(basename(x)))


def _collate(files):
    return [files[i : i + 2] for i in range(0, len(files), 2)]


def _extract_fs_fields(filenames: str | list[str]) -> tuple[str, str]:
    from pathlib import Path

    if isinstance(filenames, str):
        filenames = [filenames]
    paths = [Path(fn) for fn in filenames]
    sub_dir = paths[0].parent.parent
    subjects_dir, subject_id = sub_dir.parent, sub_dir.name
    assert all(path == subjects_dir / subject_id / 'surf' / path.name for path in paths)
    return str(subjects_dir), subject_id


def _get_surfaces(subjects_dir: str, subject_id: str, surfaces: list[str]) -> tuple[list[str]]:
    """
    Get a list of FreeSurfer surface files for a given subject.

    If ``midthickness`` is requested but not present in the directory,
    ``graymid`` will be returned instead. For surfaces with dots (``.``) in
    their names, pass the name with underscores (``_``).

    Parameters
    ----------
    subjects_dir
        FreeSurfer SUBJECTS_DIR
    subject_id
        FreeSurfer subject ID
    surfaces
        List of surfaces to fetch

    Returns
    -------
    tuple
        A list of surfaces for each requested surface, sorted

    """
    from pathlib import Path

    expanded_surfaces = surfaces.copy()
    if "midthickness" in surfaces:
        expanded_surfaces.append("graymid")

    surf_dir = Path(subjects_dir) / subject_id / "surf"
    all_surfs = {
        surface: sorted(
            str(fn)
            for fn in surf_dir.glob(f"[lr]h.{surface.replace('_', '.')}")
        )
        for surface in expanded_surfaces
    }

    if all_surfs.get("graymid") and not all_surfs.get("midthickness"):
        all_surfs["midthickness"] = all_surfs.pop("graymid")

    ret = tuple(all_surfs[surface] for surface in surfaces)
    return ret if len(ret) > 1 else ret[0]

# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
"""Anatomical reference preprocessing workflows."""
from pkg_resources import resource_filename as pkgr
from multiprocessing import cpu_count

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
    PatchedConcatenateLTA as ConcatenateLTA,
    PatchedLTAConvert as LTAConvert,
)
from niworkflows.interfaces.images import TemplateDimensions, Conform, ValidateImage
from niworkflows.interfaces.nibabel import Binarize
from niworkflows.interfaces.utils import CopyXForm
from niworkflows.utils.misc import fix_multi_T1w_source_name, add_suffix
from niworkflows.anat.ants import (
    init_brain_extraction_wf, init_atropos_wf, ATROPOS_MODELS, _pop
    )
from .norm import init_anat_norm_wf
from .outputs import init_anat_reports_wf, init_anat_derivatives_wf
from .surfaces import init_surface_recon_wf

from packaging.version import parse as parseversion, Version
from warnings import warn


def init_n4_only_wf(name='n4_only_wf',
                    omp_nthreads=None,
                    mem_gb=3.0,
                    bids_suffix='T1w',
                    atropos_refine=True,
                    atropos_use_random_seed=True,
                    atropos_model=None):
    """
    An alternative workflow to "init_brain_extraction_wf", for anatomical
    images which have already been brain extracted.


      1. Creates brain mask assuming all zero voxels are outside the brain
      2. Applies N4 bias field correction
      3. (Optional) apply ATROPOS and massage its outputs
      4. Use results from 3 to refine N4 bias field correction


    .. workflow::
        :graph2use: orig
        :simple_form: yes
        from smriprep.workflows.anatomical import init_n4_only_wf
        wf = init_n4_only_wf()


    **Parameters**

        omp_nthreads : int
            Maximum number of threads an individual process may use
        mem_gb : float
            Estimated peak memory consumption of the most hungry nodes
        bids_suffix : str
            Sequence type of the first input image. For a list of acceptable values
            see https://bids-specification.readthedocs.io/en/latest/\
04-modality-specific-files/01-magnetic-resonance-imaging-data.html#anatomy-imaging-data
        atropos_refine : bool
            Enables or disables the whole ATROPOS sub-workflow
        atropos_use_random_seed : bool
            Whether ATROPOS should generate a random seed based on the
            system's clock
        atropos_model : tuple or None
            Allows to specify a particular segmentation model, overwriting
            the defaults based on ``bids_suffix``
        name : str, optional
            Workflow name (default: antsBrainExtraction)


    **Inputs**

        in_files
            List of input anatomical images to be bias corrected,
            typically T1-weighted.
            If a list of anatomical images is provided, subsequently
            specified images are used during the segmentation process.
            However, only the first image is used in the registration
            of priors.
            Our suggestion would be to specify the T1w as the first image.


    **Outputs**


        out_file
            :abbr:`INU (intensity non-uniformity)`-corrected ``in_files``
        out_mask
            Calculated brain mask
        bias_corrected
            Same as "out_file", provided for consistency with brain extraction
        bias_image
            The :abbr:`INU (intensity non-uniformity)` field estimated for each
            input in ``in_files``
        out_segm
            Output segmentation by ATROPOS
        out_tpms
            Output :abbr:`TPMs (tissue probability maps)` by ATROPOS


    """
    wf = pe.Workflow(name)

    if omp_nthreads is None or omp_nthreads < 1:
        omp_nthreads = cpu_count()

    inputnode = pe.Node(niu.IdentityInterface(fields=['in_files', 'in_mask']),
                        name='inputnode')

    outputnode = pe.Node(niu.IdentityInterface(
        fields=['out_file', 'out_mask', 'bias_corrected', 'bias_image',
                'out_segm', 'out_tpms']),
        name='outputnode')

    # Create brain mask
    thr_brainmask = pe.Node(
        Binarize(thresh_low=0), name='binarize')

    # INU correction
    inu_n4_final = pe.MapNode(
        N4BiasFieldCorrection(
            dimension=3, save_bias=True, copy_header=True,
            n_iterations=[50] * 5, convergence_threshold=1e-7, shrink_factor=4,
            bspline_fitting_distance=200),
        n_procs=omp_nthreads, name='inu_n4_final', iterfield=['input_image'])

    # Tolerate missing ANTs at construction time
    _ants_version = N4BiasFieldCorrection().version

    if _ants_version and parseversion(_ants_version) >= Version('2.1.0'):
        inu_n4_final.inputs.rescale_intensities = True
    else:
        warn("""\
Found ANTs version %s, which is too old. Please consider upgrading to 2.1.0 or \
greater so that the --rescale-intensities option is available with \
N4BiasFieldCorrection.""" % _ants_version, DeprecationWarning)

    copy_xform = pe.Node(CopyXForm(
        fields=['out_file', 'bias_image']),
        name='copy_xform', run_without_submitting=True)

    wf.connect([
        (inputnode, inu_n4_final, [('in_files', 'input_image')]),
<<<<<<< HEAD
        (inputnode, thr_brainmask, [(('in_files', _pop), 'in_file')]),
        (thr_brainmask, outputnode, [('out_mask', 'out_mask')]),
        (inu_n4_final, outputnode, [('output_image', 'out_file')]),
        (inu_n4_final, outputnode, [('output_image', 'bias_corrected')]),
        (inu_n4_final, outputnode, [('bias_image', 'bias_image')])
=======
        (inputnode, thr_brainmask, [(('in_files', _pop), 'input_image')]),
        (thr_brainmask, outputnode, [('output_image', 'out_mask')]),
        (inu_n4_final, copy_xform, [('output_image', 'out_file')]),
        (inu_n4_final, copy_xform, [('bias_image', 'bias_image')]),
        (copy_xform, outputnode, [('out_file', 'out_file')]),
        (copy_xform, outputnode, [('out_file', 'bias_corrected')]),
        (copy_xform, outputnode, [('bias_image', 'bias_image')])
>>>>>>> Fix connection
    ])

    # If atropos refine, do in4 twice
    if atropos_refine:
        atropos_model = atropos_model or list(
            ATROPOS_MODELS[bids_suffix].values())
        atropos_wf = init_atropos_wf(
            use_random_seed=atropos_use_random_seed,
            omp_nthreads=omp_nthreads,
            mem_gb=mem_gb,
            in_segmentation_model=atropos_model,
        )
        sel_wm = pe.Node(niu.Select(index=atropos_model[-1] - 1), name='sel_wm',
                         run_without_submitting=True)

        inu_n4 = pe.MapNode(
            N4BiasFieldCorrection(
                dimension=3, save_bias=False, copy_header=True,
                n_iterations=[50] * 4, convergence_threshold=1e-7,
                shrink_factor=4, bspline_fitting_distance=200),
            n_procs=omp_nthreads, name='inu_n4', iterfield=['input_image'])

        wf.connect([
            (inputnode, inu_n4, [('in_files', 'input_image')]),
            (inu_n4, atropos_wf, [
                ('output_image', 'inputnode.in_files')]),
            (thr_brainmask, atropos_wf, [
                ('out_mask', 'inputnode.in_mask')]),
            (thr_brainmask, atropos_wf, [
                ('out_mask', 'inputnode.in_mask_dilated')]),  # Dilate?
            (atropos_wf, sel_wm, [('outputnode.out_tpms', 'inlist')]),
            (sel_wm, inu_n4_final, [('out', 'weight_image')]),
            (atropos_wf, outputnode, [
                ('outputnode.out_segm', 'out_segm'),
                ('outputnode.out_tpms', 'out_tpms')]),
        ])

    return wf


def init_anat_preproc_wf(
        bids_root,
        freesurfer,
        hires,
        longitudinal,
        num_t1w,
        omp_nthreads,
        output_dir,
        reportlets_dir,
        skull_strip_template,
        spaces,
        debug=False,
        name='anat_preproc_wf',
        skull_strip_fixed_seed=False,
        skip_brain_extraction=False,
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
                num_t1w=1,
                omp_nthreads=1,
                output_dir='.',
                reportlets_dir='.',
                skull_strip_template=Reference('OASIS30ANTs'),
                spaces=SpatialReferences(spaces=['MNI152NLin2009cAsym', 'fsaverage5']),
            )

    Parameters
    ----------
    bids_root : :obj:`str`
        Path of the input BIDS dataset root
    freesurfer : :obj:`bool`
        Enable FreeSurfer surface reconstruction (increases runtime by 6h,
        at the very least)
    hires : :obj:`bool`
        Enable sub-millimeter preprocessing in FreeSurfer
    longitudinal : :obj:`bool`
        Create unbiased structural template, regardless of number of inputs
        (may increase runtime)
    num_t1w : :obj:`int`
        Number of T1w that were averaged for the anatomical reference.
    omp_nthreads : :obj:`int`
        Maximum number of threads an individual process may use
    output_dir : :obj:`str`
        Directory in which to save derivatives
    reportlets_dir : :obj:`str`
        Directory in which to save reportlets
    skull_strip_template : :py:class:`~niworkflows.utils.spaces.Reference`
        Spatial reference to use in atlas-based brain extraction.
    spaces : :py:class:`~niworkflows.utils.spaces.SpatialReferences`
        Object containing standard and nonstandard space specifications.
    debug : :obj:`bool`
        Enable debugging outputs
    name : :obj:`str`, optional
        Workflow name (default: anat_preproc_wf)
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
    flair
        List of FLAIR images
    subjects_dir
        FreeSurfer SUBJECTS_DIR

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
    std_t1w
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
    desc = """Anatomical data preprocessing

: """
    desc += """\
A total of {num_t1w} T1-weighted (T1w) images were found within the input
BIDS dataset.
All of them were corrected for intensity non-uniformity (INU)
""" if num_t1w > 1 else """\
The T1-weighted (T1w) image was corrected for intensity non-uniformity (INU)
"""
    desc += """\
with `N4BiasFieldCorrection` [@n4], distributed with ANTs {ants_ver} \
[@ants, RRID:SCR_004757]"""
    desc += '.\n' if num_t1w > 1 else ", and used as T1w-reference throughout the workflow.\n"

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
        ants_ver=ANTsInfo.version() or '(version unknown)',
        fsl_ver=fsl.FAST().version or '(version unknown)',
        num_t1w=num_t1w,
        skullstrip_tpl=skull_strip_template.fullname,
    )

    inputnode = pe.Node(
        niu.IdentityInterface(fields=['t1w', 't2w', 'roi', 'flair', 'subjects_dir', 'subject_id']),
        name='inputnode')
    outputnode = pe.Node(niu.IdentityInterface(
        fields=['t1w_preproc', 't1w_brain', 't1w_mask', 't1w_dseg', 't1w_tpms',
                'template', 'std_t1w', 'anat2std_xfm', 'std2anat_xfm',
                'joint_template', 'joint_anat2std_xfm', 'joint_std2anat_xfm',
                'std_mask', 'std_dseg', 'std_tpms', 't1w_realign_xfm',
                'subjects_dir', 'subject_id', 't1w2fsnative_xfm',
                'fsnative2t1w_xfm', 'surfaces', 't1w_aseg', 't1w_aparc']),
        name='outputnode')

    buffernode = pe.Node(niu.IdentityInterface(
        fields=['t1w_brain', 't1w_mask']), name='buffernode')

    # 1. Anatomical reference generation - average input T1w images.
    anat_template_wf = init_anat_template_wf(longitudinal=longitudinal, omp_nthreads=omp_nthreads,
                                             num_t1w=num_t1w)

    anat_validate = pe.Node(ValidateImage(), name='anat_validate',
                            run_without_submitting=True)

    # 2. Brain-extraction and INU (bias field) correction.
    if not skip_brain_extraction:
        brain_extraction_wf = init_brain_extraction_wf(
            in_template=skull_strip_template.space,
            template_spec=skull_strip_template.spec,
            atropos_use_random_seed=not skull_strip_fixed_seed,
            omp_nthreads=omp_nthreads,
            normalization_quality='precise' if not debug else 'testing')
    else:
        brain_extraction_wf = init_n4_only_wf(
            omp_nthreads=omp_nthreads,
            atropos_use_random_seed=not skull_strip_fixed_seed
        )

    # 3. Brain tissue segmentation
    t1w_dseg = pe.Node(fsl.FAST(segments=True, no_bias=True, probability_maps=True),
                       name='t1w_dseg', mem_gb=3)

    workflow.connect([
        (buffernode, t1w_dseg, [('t1w_brain', 'in_files')]),
        (t1w_dseg, outputnode, [('tissue_class_map', 't1w_dseg'),
                                ('probability_maps', 't1w_tpms')]),
    ])

    # 4. Spatial normalization
    anat_norm_wf = init_anat_norm_wf(
        debug=debug,
        omp_nthreads=omp_nthreads,
        templates=spaces.get_spaces(nonstandard=False, dim=(3,)),
    )

    workflow.connect([
        # Step 1.
        (inputnode, anat_template_wf, [('t1w', 'inputnode.t1w')]),
        (anat_template_wf, anat_validate, [
            ('outputnode.t1w_ref', 'in_file')]),
        (anat_validate, brain_extraction_wf, [
            ('out_file', 'inputnode.in_files')]),
        (brain_extraction_wf, outputnode, [
            ('outputnode.bias_corrected', 't1w_preproc')]),
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
        (t1w_dseg, anat_norm_wf, [
            ('tissue_class_map', 'inputnode.moving_segmentation')]),
        (t1w_dseg, anat_norm_wf, [
            ('probability_maps', 'inputnode.moving_tpms')]),
        (anat_norm_wf, outputnode, [
            ('poutputnode.standardized', 'std_t1w'),
            ('poutputnode.template', 'template'),
            ('poutputnode.anat2std_xfm', 'anat2std_xfm'),
            ('poutputnode.std2anat_xfm', 'std2anat_xfm'),
            ('poutputnode.std_mask', 'std_mask'),
            ('poutputnode.std_dseg', 'std_dseg'),
            ('poutputnode.std_tpms', 'std_tpms'),
            ('outputnode.template', 'joint_template'),
            ('outputnode.anat2std_xfm', 'joint_anat2std_xfm'),
            ('outputnode.std2anat_xfm', 'joint_std2anat_xfm'),
        ]),
    ])

    # Write outputs ############################################3
    anat_reports_wf = init_anat_reports_wf(
        reportlets_dir=reportlets_dir, freesurfer=freesurfer)

    anat_derivatives_wf = init_anat_derivatives_wf(
        bids_root=bids_root,
        freesurfer=freesurfer,
        num_t1w=num_t1w,
        output_dir=output_dir,
    )

    workflow.connect([
        # Connect reportlets
        (inputnode, anat_reports_wf, [
            (('t1w', fix_multi_T1w_source_name), 'inputnode.source_file')]),
        (anat_template_wf, anat_reports_wf, [
            ('outputnode.out_report', 'inputnode.t1w_conform_report')]),
        (outputnode, anat_reports_wf, [
            ('t1w_preproc', 'inputnode.t1w_preproc'),
            ('t1w_dseg', 'inputnode.t1w_dseg'),
            ('t1w_mask', 'inputnode.t1w_mask'),
            ('std_t1w', 'inputnode.std_t1w'),
            ('std_mask', 'inputnode.std_mask')]),
        (anat_norm_wf, anat_reports_wf, [
            ('poutputnode.template', 'inputnode.template'),
            ('poutputnode.template_spec', 'inputnode.template_spec')]),
        # Connect derivatives
        (anat_template_wf, anat_derivatives_wf, [
            ('outputnode.t1w_valid_list', 'inputnode.source_files')]),
        (anat_norm_wf, anat_derivatives_wf, [
            ('poutputnode.template', 'inputnode.template')]),
        (outputnode, anat_derivatives_wf, [
            ('std_t1w', 'inputnode.std_t1w'),
            ('anat2std_xfm', 'inputnode.anat2std_xfm'),
            ('std2anat_xfm', 'inputnode.std2anat_xfm'),
            ('t1w_ref_xfms', 'inputnode.t1w_ref_xfms'),
            ('t1w_preproc', 'inputnode.t1w_preproc'),
            ('t1w_mask', 'inputnode.t1w_mask'),
            ('t1w_dseg', 'inputnode.t1w_dseg'),
            ('t1w_tpms', 'inputnode.t1w_tpms'),
            ('std_mask', 'inputnode.std_mask'),
            ('std_dseg', 'inputnode.std_dseg'),
            ('std_tpms', 'inputnode.std_tpms'),
            ('t1w2fsnative_xfm', 'inputnode.t1w2fsnative_xfm'),
            ('fsnative2t1w_xfm', 'inputnode.fsnative2t1w_xfm'),
            ('surfaces', 'inputnode.surfaces'),
        ]),
    ])

    if not freesurfer:  # Flag --fs-no-reconall is set - return
        workflow.connect([
            (brain_extraction_wf, buffernode, [
                (('outputnode.out_file', _pop), 't1w_brain'),
                ('outputnode.out_mask', 't1w_mask')]),
        ])
        return workflow

    # 5. Surface reconstruction (--fs-no-reconall not set)
    surface_recon_wf = init_surface_recon_wf(name='surface_recon_wf',
                                             omp_nthreads=omp_nthreads, hires=hires)
    applyrefined = pe.Node(fsl.ApplyMask(), name='applyrefined')
    workflow.connect([
        (inputnode, surface_recon_wf, [
            ('t2w', 'inputnode.t2w'),
            ('flair', 'inputnode.flair'),
            ('subjects_dir', 'inputnode.subjects_dir'),
            ('subject_id', 'inputnode.subject_id')]),
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
    ])

    return workflow


def init_anat_template_wf(longitudinal, omp_nthreads, num_t1w, name='anat_template_wf'):
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
""".format(num_t1w=num_t1w, fs_ver=fs.Info().looseversion() or '<ver>')

    inputnode = pe.Node(niu.IdentityInterface(fields=['t1w']), name='inputnode')
    outputnode = pe.Node(niu.IdentityInterface(
        fields=['t1w_ref', 't1w_valid_list', 't1w_realign_xfm', 'out_report']),
        name='outputnode')

    # 0. Reorient T1w image(s) to RAS and resample to common voxel space
    t1w_ref_dimensions = pe.Node(TemplateDimensions(), name='t1w_ref_dimensions')
    t1w_conform = pe.MapNode(Conform(), iterfield='in_file', name='t1w_conform')

    workflow.connect([
        (inputnode, t1w_ref_dimensions, [('t1w', 't1w_list')]),
        (t1w_ref_dimensions, t1w_conform, [
            ('t1w_valid_list', 'in_file'),
            ('target_zooms', 'target_zooms'),
            ('target_shape', 'target_shape')]),
        (t1w_ref_dimensions, outputnode, [('out_report', 'out_report'),
                                          ('t1w_valid_list', 't1w_valid_list')]),
    ])

    if num_t1w == 1:
        get1st = pe.Node(niu.Select(index=[0]), name='get1st')
        outputnode.inputs.t1w_realign_xfm = [pkgr('smriprep', 'data/itkIdentityTransform.txt')]

        workflow.connect([
            (t1w_conform, get1st, [('out_file', 'inlist')]),
            (get1st, outputnode, [('out', 't1w_ref')]),
        ])

        return workflow

    t1w_conform_xfm = pe.MapNode(LTAConvert(in_lta='identity.nofile', out_lta=True),
                                 iterfield=['source_file', 'target_file'],
                                 name='t1w_conform_xfm')

    # 1. Template (only if several T1w images)
    # 1a. Correct for bias field: the bias field is an additive factor
    #     in log-transformed intensity units. Therefore, it is not a linear
    #     combination of fields and N4 fails with merged images.
    # 1b. Align and merge if several T1w images are provided
    n4_correct = pe.MapNode(
        N4BiasFieldCorrection(dimension=3, copy_header=True),
        iterfield='input_image', name='n4_correct',
        n_procs=1)  # n_procs=1 for reproducibility
    # StructuralReference is fs.RobustTemplate if > 1 volume, copying otherwise
    t1w_merge = pe.Node(
        StructuralReference(auto_detect_sensitivity=True,
                            initial_timepoint=1,      # For deterministic behavior
                            intensity_scaling=True,   # 7-DOF (rigid + intensity)
                            subsample_threshold=200,
                            fixed_timepoint=not longitudinal,
                            no_iteration=not longitudinal,
                            transform_outputs=True,
                            ),
        mem_gb=2 * num_t1w - 1,
        name='t1w_merge')

    # 2. Reorient template to RAS, if needed (mri_robust_template may set to LIA)
    t1w_reorient = pe.Node(image.Reorient(), name='t1w_reorient')

    concat_affines = pe.MapNode(
        ConcatenateLTA(out_type='RAS2RAS', invert_out=True),
        iterfield=['in_lta1', 'in_lta2'],
        name='concat_affines')

    lta_to_itk = pe.MapNode(LTAConvert(out_itk=True), iterfield=['in_lta'], name='lta_to_itk')

    def _set_threads(in_list, maximum):
        return min(len(in_list), maximum)

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
        (t1w_conform_xfm, concat_affines, [('out_lta', 'in_lta1')]),
        (t1w_merge, concat_affines, [('transform_outputs', 'in_lta2')]),
        (concat_affines, lta_to_itk, [('out_file', 'in_lta')]),
        # Output
        (t1w_reorient, outputnode, [('out_file', 't1w_ref')]),
        (lta_to_itk, outputnode, [('out_itk', 't1w_realign_xfm')]),
    ])

    return workflow


def _pop(inlist):
    if isinstance(inlist, (list, tuple)):
        return inlist[0]
    return inlist

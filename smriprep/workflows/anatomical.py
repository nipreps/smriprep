# -*- coding: utf-8 -*-
# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
"""
Anatomical reference preprocessing workflows
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. autofunction:: init_anat_preproc_wf

"""

from pkg_resources import resource_filename as pkgr

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
from niworkflows.interfaces.masks import ROIsPlot
from niworkflows.interfaces.freesurfer import (
    StructuralReference,
    PatchedConcatenateLTA as ConcatenateLTA,
    PatchedLTAConvert as LTAConvert,
)
from niworkflows.interfaces.images import TemplateDimensions, Conform
from niworkflows.utils.misc import fix_multi_T1w_source_name, add_suffix
from niworkflows.anat.ants import init_brain_extraction_wf
from .norm import init_anat_norm_wf
from .outputs import init_anat_reports_wf, init_anat_derivatives_wf
from .surfaces import init_surface_recon_wf


#  pylint: disable=R0914
def init_anat_preproc_wf(
        bids_root, freesurfer, hires, longitudinal, omp_nthreads, output_dir,
        output_spaces, num_t1w, reportlets_dir, skull_strip_template,
        debug=False, name='anat_preproc_wf', skull_strip_fixed_seed=False):
    r"""
    This workflow controls the anatomical preprocessing stages of smriprep.

    This includes:

     - Creation of a structural template
     - Skull-stripping and bias correction
     - Tissue segmentation
     - Normalization
     - Surface reconstruction with FreeSurfer

    .. workflow::
        :graph2use: orig
        :simple_form: yes

        from smriprep.workflows.anatomical import init_anat_preproc_wf
        wf = init_anat_preproc_wf(
            bids_root='.',
            freesurfer=True,
            hires=True,
            longitudinal=False,
            num_t1w=1,
            omp_nthreads=1,
            output_dir='.',
            output_spaces={'MNI152NLin2009cAsym': {}, 'fsnative': {}, 'fsaverage5': {}},
            reportlets_dir='.',
            skull_strip_template='MNI152NLin2009cAsym',
        )

    **Parameters**

        bids_root : str
            Path of the input BIDS dataset root
        debug : bool
            Enable debugging outputs
        freesurfer : bool
            Enable FreeSurfer surface reconstruction (increases runtime by 6h, at the very least)
        output_spaces : list
            List of spatial normalization targets. Some parts of pipeline will
            only be instantiated for some output spaces. Valid spaces:
              - Any template identifier from TemplateFlow
              - Path to a template folder organized following TemplateFlow's conventions
        hires : bool
            Enable sub-millimeter preprocessing in FreeSurfer
        longitudinal : bool
            Create unbiased structural template, regardless of number of inputs
            (may increase runtime)
        name : str, optional
            Workflow name (default: anat_preproc_wf)
        omp_nthreads : int
            Maximum number of threads an individual process may use
        output_dir : str
            Directory in which to save derivatives
        reportlets_dir : str
            Directory in which to save reportlets
        skull_strip_fixed_seed : bool
            Do not use a random seed for skull-stripping - will ensure
            run-to-run replicability when used with --omp-nthreads 1 (default: ``False``)
        skull_strip_template : str
            Name of ANTs skull-stripping template ('MNI152NLin2009cAsym', 'OASIS30ANTs' or 'NKI')


    **Inputs**

        t1w
            List of T1-weighted structural images
        t2w
            List of T2-weighted structural images
        flair
            List of FLAIR images
        subjects_dir
            FreeSurfer SUBJECTS_DIR


    **Outputs**

        t1_preproc
            Bias-corrected structural template, defining T1w space
        t1_brain
            Skull-stripped ``t1_preproc``
        t1_mask
            Mask of the skull-stripped template image
        t1_seg
            Segmentation of preprocessed structural image, including
            gray-matter (GM), white-matter (WM) and cerebrospinal fluid (CSF)
        t1_tpms
            List of tissue probability maps in T1w space
        t1_2_tpl
            T1w template, normalized to MNI space
        t1_2_tpl_forward_transform
            ANTs-compatible affine-and-warp transform file
        t1_2_tpl_reverse_transform
            ANTs-compatible affine-and-warp transform file (inverse)
        tpl_mask
            Mask of skull-stripped template, in MNI space
        tpl_seg
            Segmentation, resampled into MNI space
        tpl_tpms
            List of tissue probability maps in MNI space
        subjects_dir
            FreeSurfer SUBJECTS_DIR
        subject_id
            FreeSurfer subject ID
        t1_2_fsnative_forward_transform
            LTA-style affine matrix translating from T1w to FreeSurfer-conformed subject space
        t1_2_fsnative_reverse_transform
            LTA-style affine matrix translating from FreeSurfer-conformed subject space to T1w
        surfaces
            GIFTI surfaces (gray/white boundary, midthickness, pial, inflated)

    **Subworkflows**

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
        skullstrip_tpl=skull_strip_template,
    )

    inputnode = pe.Node(
        niu.IdentityInterface(fields=['t1w', 't2w', 'roi', 'flair', 'subjects_dir', 'subject_id']),
        name='inputnode')
    outputnode = pe.Node(niu.IdentityInterface(
        fields=['t1_preproc', 't1_brain', 't1_mask', 't1_seg', 't1_tpms',
                'warped', 'forward_transform', 'reverse_transform',
                'tpl_mask', 'tpl_seg', 'tpl_tpms',
                'template_transforms',
                'subjects_dir', 'subject_id', 't1_2_fsnative_forward_transform',
                't1_2_fsnative_reverse_transform', 'surfaces', 't1_aseg', 't1_aparc']),
        name='outputnode')

    buffernode = pe.Node(niu.IdentityInterface(
        fields=['t1_brain', 't1_mask']), name='buffernode')

    anat_template_wf = init_anat_template_wf(longitudinal=longitudinal, omp_nthreads=omp_nthreads,
                                             num_t1w=num_t1w)

    # 3. Skull-stripping
    # Bias field correction is handled in skull strip workflows.
    brain_extraction_wf = init_brain_extraction_wf(
        in_template=skull_strip_template,
        atropos_use_random_seed=not skull_strip_fixed_seed,
        omp_nthreads=omp_nthreads,
        normalization_quality='precise' if not debug else 'testing')

    workflow.connect([
        (inputnode, anat_template_wf, [('t1w', 'inputnode.t1w')]),
        (anat_template_wf, brain_extraction_wf, [
            ('outputnode.t1_template', 'inputnode.in_files')]),
        (brain_extraction_wf, outputnode, [
            ('outputnode.bias_corrected', 't1_preproc')]),
        (anat_template_wf, outputnode, [
            ('outputnode.template_transforms', 't1_template_transforms')]),
        (buffernode, outputnode, [('t1_brain', 't1_brain'),
                                  ('t1_mask', 't1_mask')]),
    ])

    # 4. Surface reconstruction
    if freesurfer:
        surface_recon_wf = init_surface_recon_wf(name='surface_recon_wf',
                                                 omp_nthreads=omp_nthreads, hires=hires)
        applyrefined = pe.Node(fsl.ApplyMask(), name='applyrefined')
        workflow.connect([
            (inputnode, surface_recon_wf, [
                ('t2w', 'inputnode.t2w'),
                ('flair', 'inputnode.flair'),
                ('subjects_dir', 'inputnode.subjects_dir'),
                ('subject_id', 'inputnode.subject_id')]),
            (anat_template_wf, surface_recon_wf, [('outputnode.t1_template', 'inputnode.t1w')]),
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
                ('outputnode.t1_2_fsnative_forward_transform', 't1_2_fsnative_forward_transform'),
                ('outputnode.t1_2_fsnative_reverse_transform', 't1_2_fsnative_reverse_transform'),
                ('outputnode.surfaces', 'surfaces'),
                ('outputnode.out_aseg', 't1_aseg'),
                ('outputnode.out_aparc', 't1_aparc')]),
            (applyrefined, buffernode, [('out_file', 't1_brain')]),
            (surface_recon_wf, buffernode, [
                ('outputnode.out_brainmask', 't1_mask')]),
        ])
    else:
        workflow.connect([
            (brain_extraction_wf, buffernode, [
                (('outputnode.out_file', _pop), 't1_brain'),
                ('outputnode.out_mask', 't1_mask')]),
        ])

    # 5. Segmentation
    t1_seg = pe.Node(fsl.FAST(segments=True, no_bias=True, probability_maps=True),
                     name='t1_seg', mem_gb=3)

    workflow.connect([
        (buffernode, t1_seg, [('t1_brain', 'in_files')]),
        (t1_seg, outputnode, [('tissue_class_map', 't1_seg'),
                              ('probability_maps', 't1_tpms')]),
    ])

    seg_rpt = pe.Node(ROIsPlot(colors=['magenta', 'b'], levels=[1.5, 2.5]),
                      name='seg_rpt')

    vol_spaces = [k for k in output_spaces.keys()
                  if not k.startswith('fs')]
    # 6. Spatial normalization
    anat_norm_wf = init_anat_norm_wf(
        debug=debug,
        omp_nthreads=omp_nthreads,
        reportlets_dir=reportlets_dir,
        template_list=vol_spaces)
    workflow.connect([
        (inputnode, anat_norm_wf, [
            (('t1w', fix_multi_T1w_source_name), 'inputnode.orig_t1w'),
            ('roi', 'inputnode.lesion_mask')]),
        (brain_extraction_wf, anat_norm_wf, [
            (('outputnode.bias_corrected', _pop), 'inputnode.moving_image')]),
        (buffernode, anat_norm_wf, [('t1_mask', 'inputnode.moving_mask')]),
        (t1_seg, anat_norm_wf, [
            ('tissue_class_map', 'inputnode.moving_segmentation')]),
        (t1_seg, anat_norm_wf, [
            ('probability_maps', 'inputnode.moving_tpms')]),
        (anat_norm_wf, outputnode, [
            ('outputnode.warped', 'warped'),
            ('outputnode.forward_transform', 'forward_transform'),
            ('outputnode.reverse_transform', 'reverse_transform'),
            ('outputnode.tpl_mask', 'tpl_mask'),
            ('outputnode.tpl_seg', 'tpl_seg'),
            ('outputnode.tpl_tpms', 'tpl_tpms')]),
    ])
    anat_reports_wf = init_anat_reports_wf(
        reportlets_dir=reportlets_dir, freesurfer=freesurfer)
    workflow.connect([
        (inputnode, anat_reports_wf, [
            (('t1w', fix_multi_T1w_source_name), 'inputnode.source_file')]),
        (anat_template_wf, anat_reports_wf, [
            ('outputnode.out_report', 'inputnode.t1_conform_report')]),
        (anat_template_wf, seg_rpt, [
            ('outputnode.t1_template', 'in_file')]),
        (t1_seg, seg_rpt, [('tissue_class_map', 'in_rois')]),
        (outputnode, seg_rpt, [('t1_mask', 'in_mask')]),
        (seg_rpt, anat_reports_wf, [('out_report', 'inputnode.seg_report')]),
    ])

    if freesurfer:
        workflow.connect([
            (surface_recon_wf, anat_reports_wf, [
                ('outputnode.out_report', 'inputnode.recon_report')]),
        ])

    anat_derivatives_wf = init_anat_derivatives_wf(
        bids_root=bids_root,
        freesurfer=freesurfer,
        output_dir=output_dir,
    )

    workflow.connect([
        (anat_template_wf, anat_derivatives_wf, [
            ('outputnode.t1w_valid_list', 'inputnode.source_files')]),
        (anat_norm_wf, anat_derivatives_wf, [
            ('outputnode.template', 'inputnode.template')]),
        (outputnode, anat_derivatives_wf, [
            ('warped', 'inputnode.t1_2_tpl'),
            ('forward_transform', 'inputnode.t1_2_tpl_forward_transform'),
            ('reverse_transform', 'inputnode.t1_2_tpl_reverse_transform'),
            ('t1_template_transforms', 'inputnode.t1_template_transforms'),
            ('t1_preproc', 'inputnode.t1_preproc'),
            ('t1_mask', 'inputnode.t1_mask'),
            ('t1_seg', 'inputnode.t1_seg'),
            ('t1_tpms', 'inputnode.t1_tpms'),
            ('tpl_mask', 'inputnode.tpl_mask'),
            ('tpl_seg', 'inputnode.tpl_seg'),
            ('tpl_tpms', 'inputnode.tpl_tpms'),
            ('t1_2_fsnative_forward_transform', 'inputnode.t1_2_fsnative_forward_transform'),
            ('surfaces', 'inputnode.surfaces'),
        ]),
    ])

    if freesurfer:
        workflow.connect([
            (surface_recon_wf, anat_derivatives_wf, [
                ('outputnode.out_aseg', 'inputnode.t1_fs_aseg'),
                ('outputnode.out_aparc', 'inputnode.t1_fs_aparc'),
            ]),
        ])

    return workflow


def init_anat_template_wf(longitudinal, omp_nthreads, num_t1w, name='anat_template_wf'):
    r"""
    This workflow generates a canonically oriented structural template from
    input T1w images.


    .. workflow::
        :graph2use: orig
        :simple_form: yes

        from smriprep.workflows.anatomical import init_anat_template_wf
        wf = init_anat_template_wf(longitudinal=False, omp_nthreads=1, num_t1w=1)

    **Parameters**

        longitudinal : bool
            Create unbiased structural template, regardless of number of inputs
            (may increase runtime)
        omp_nthreads : int
            Maximum number of threads an individual process may use
        num_t1w : int
            Number of T1w images
        name : str, optional
            Workflow name (default: anat_template_wf)


    **Inputs**

        t1w
            List of T1-weighted structural images


    **Outputs**

        t1_template
            Structural template, defining T1w space
        template_transforms
            List of affine transforms from ``t1_template`` to original T1w images
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
        fields=['t1_template', 't1w_valid_list', 'template_transforms', 'out_report']),
        name='outputnode')

    # 0. Reorient T1w image(s) to RAS and resample to common voxel space
    t1_template_dimensions = pe.Node(TemplateDimensions(), name='t1_template_dimensions')
    t1_conform = pe.MapNode(Conform(), iterfield='in_file', name='t1_conform')

    workflow.connect([
        (inputnode, t1_template_dimensions, [('t1w', 't1w_list')]),
        (t1_template_dimensions, t1_conform, [
            ('t1w_valid_list', 'in_file'),
            ('target_zooms', 'target_zooms'),
            ('target_shape', 'target_shape')]),
        (t1_template_dimensions, outputnode, [('out_report', 'out_report'),
                                              ('t1w_valid_list', 't1w_valid_list')]),
    ])

    if num_t1w == 1:
        get1st = pe.Node(niu.Select(index=[0]), name='get1st')
        outputnode.inputs.template_transforms = [pkgr('smriprep', 'data/itkIdentityTransform.txt')]

        workflow.connect([
            (t1_conform, get1st, [('out_file', 'inlist')]),
            (get1st, outputnode, [('out', 't1_template')]),
        ])

        return workflow

    t1_conform_xfm = pe.MapNode(LTAConvert(in_lta='identity.nofile', out_lta=True),
                                iterfield=['source_file', 'target_file'],
                                name='t1_conform_xfm')

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
    t1_merge = pe.Node(
        StructuralReference(auto_detect_sensitivity=True,
                            initial_timepoint=1,      # For deterministic behavior
                            intensity_scaling=True,   # 7-DOF (rigid + intensity)
                            subsample_threshold=200,
                            fixed_timepoint=not longitudinal,
                            no_iteration=not longitudinal,
                            transform_outputs=True,
                            ),
        mem_gb=2 * num_t1w - 1,
        name='t1_merge')

    # 2. Reorient template to RAS, if needed (mri_robust_template may set to LIA)
    t1_reorient = pe.Node(image.Reorient(), name='t1_reorient')

    concat_affines = pe.MapNode(
        ConcatenateLTA(out_type='RAS2RAS', invert_out=True),
        iterfield=['in_lta1', 'in_lta2'],
        name='concat_affines')

    lta_to_itk = pe.MapNode(LTAConvert(out_itk=True), iterfield=['in_lta'], name='lta_to_itk')

    def _set_threads(in_list, maximum):
        return min(len(in_list), maximum)

    workflow.connect([
        (t1_template_dimensions, t1_conform_xfm, [('t1w_valid_list', 'source_file')]),
        (t1_conform, t1_conform_xfm, [('out_file', 'target_file')]),
        (t1_conform, n4_correct, [('out_file', 'input_image')]),
        (t1_conform, t1_merge, [
            (('out_file', _set_threads, omp_nthreads), 'num_threads'),
            (('out_file', add_suffix, '_template'), 'out_file')]),
        (n4_correct, t1_merge, [('output_image', 'in_files')]),
        (t1_merge, t1_reorient, [('out_file', 'in_file')]),
        # Combine orientation and template transforms
        (t1_conform_xfm, concat_affines, [('out_lta', 'in_lta1')]),
        (t1_merge, concat_affines, [('transform_outputs', 'in_lta2')]),
        (concat_affines, lta_to_itk, [('out_file', 'in_lta')]),
        # Output
        (t1_reorient, outputnode, [('out_file', 't1_template')]),
        (lta_to_itk, outputnode, [('out_itk', 'template_transforms')]),
    ])

    return workflow


def _pop(inlist):
    if isinstance(inlist, (list, tuple)):
        return inlist[0]
    return inlist

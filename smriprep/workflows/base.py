#!/usr/bin/env python
# -*- coding: utf-8 -*-
# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
"""
fMRIprep base processing workflows
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. autofunction:: init_smriprep_wf
.. autofunction:: init_single_subject_wf

"""

import sys
import os
from copy import deepcopy

from nipype import __version__ as nipype_ver
from nipype.pipeline import engine as pe
from nipype.interfaces import utility as niu

from niworkflows.engine.workflows import LiterateWorkflow as Workflow
from niworkflows.interfaces.bids import (
    BIDSInfo, BIDSDataGrabber, BIDSFreeSurferDir
)
from niworkflows.utils.bids import collect_data
from niworkflows.utils.misc import fix_multi_T1w_source_name

from ..interfaces import DerivativesDataSink
from ..__about__ import __version__

from .anatomical import init_anat_preproc_wf


def init_smriprep_wf(subject_list, run_uuid, work_dir, output_dir, bids_dir,
                     debug, low_mem, longitudinal, omp_nthreads,
                     skull_strip_template, skull_strip_fixed_seed,
                     freesurfer, fs_spaces, template, hires):
    """
    This workflow organizes the execution of FMRIPREP, with a sub-workflow for
    each subject.

    If FreeSurfer's recon-all is to be run, a FreeSurfer derivatives folder is
    created and populated with any needed template subjects.

    .. workflow::
        :graph2use: orig
        :simple_form: yes

        import os
        os.environ['FREESURFER_HOME'] = os.getcwd()
        from smriprep.workflows.base import init_smriprep_wf
        wf = init_smriprep_wf(subject_list=['smripreptest'],
                              task_id='',
                              echo_idx=None,
                              run_uuid='X',
                              work_dir='.',
                              output_dir='.',
                              bids_dir='.',
                              ignore=[],
                              debug=False,
                              low_mem=False,
                              anat_only=False,
                              longitudinal=False,
                              t2s_coreg=False,
                              omp_nthreads=1,
                              skull_strip_template='OASIS30ANTs',
                              skull_strip_fixed_seed=False,
                              freesurfer=True,
                              fs_spaces=['T1w', 'fsnative',
                                            'template', 'fsaverage5'],
                              template='MNI152NLin2009cAsym',
                              medial_surface_nan=False,
                              cifti_output=False,
                              hires=True,
                              use_bbr=True,
                              bold2t1w_dof=9,
                              fmap_bspline=False,
                              fmap_demean=True,
                              use_syn=True,
                              force_syn=True,
                              use_aroma=False,
                              ignore_aroma_err=False,
                              aroma_melodic_dim=-200)


    Parameters

        subject_list : list
            List of subject labels
        task_id : str or None
            Task ID of BOLD series to preprocess, or ``None`` to preprocess all
        echo_idx : int or None
            Index of echo to preprocess in multiecho BOLD series,
            or ``None`` to preprocess all
        run_uuid : str
            Unique identifier for execution instance
        work_dir : str
            Directory in which to store workflow execution state and temporary files
        output_dir : str
            Directory in which to save derivatives
        bids_dir : str
            Root directory of BIDS dataset
        ignore : list
            Preprocessing steps to skip (may include "slicetiming", "fieldmaps")
        debug : bool
            Enable debugging outputs
        low_mem : bool
            Write uncompressed .nii files in some cases to reduce memory usage
        anat_only : bool
            Disable functional workflows
        longitudinal : bool
            Treat multiple sessions as longitudinal (may increase runtime)
            See sub-workflows for specific differences
        t2s_coreg : bool
            For multi-echo EPI, use the calculated T2*-map for T2*-driven coregistration
        omp_nthreads : int
            Maximum number of threads an individual process may use
        skull_strip_template : str
            Name of ANTs skull-stripping template ('OASIS30ANTs' or 'NKI')
        skull_strip_fixed_seed : bool
            Do not use a random seed for skull-stripping - will ensure
            run-to-run replicability when used with --omp-nthreads 1
        freesurfer : bool
            Enable FreeSurfer surface reconstruction (may increase runtime)
        fs_spaces : list
            List of output spaces functional images are to be resampled to.
            Some parts of pipeline will only be instantiated for some output spaces.

            Valid spaces:

             - T1w
             - template
             - fsnative
             - fsaverage (or other pre-existing FreeSurfer templates)
        template : str
            Name of template targeted by ``template`` output space
        medial_surface_nan : bool
            Replace medial wall values with NaNs on functional GIFTI files
        cifti_output : bool
            Generate bold CIFTI file in output spaces
        hires : bool
            Enable sub-millimeter preprocessing in FreeSurfer
        use_bbr : bool or None
            Enable/disable boundary-based registration refinement.
            If ``None``, test BBR result for distortion before accepting.
        bold2t1w_dof : 6, 9 or 12
            Degrees-of-freedom for BOLD-T1w registration
        fmap_bspline : bool
            **Experimental**: Fit B-Spline field using least-squares
        fmap_demean : bool
            Demean voxel-shift map during unwarp
        use_syn : bool
            **Experimental**: Enable ANTs SyN-based susceptibility distortion correction (SDC).
            If fieldmaps are present and enabled, this is not run, by default.
        force_syn : bool
            **Temporary**: Always run SyN-based SDC
        use_aroma : bool
            Perform ICA-AROMA on MNI-resampled functional series
        ignore_aroma_err : bool
            Do not fail on ICA-AROMA errors

    """
    smriprep_wf = Workflow(name='smriprep_wf')
    smriprep_wf.base_dir = work_dir

    if freesurfer:
        fsdir = pe.Node(
            BIDSFreeSurferDir(
                derivatives=output_dir,
                freesurfer_home=os.getenv('FREESURFER_HOME'),
                spaces=fs_spaces),
            name='fsdir_run_' + run_uuid.replace('-', '_'), run_without_submitting=True)

    reportlets_dir = os.path.join(work_dir, 'reportlets')
    for subject_id in subject_list:
        single_subject_wf = init_single_subject_wf(
            subject_id=subject_id,
            name="single_subject_" + subject_id + "_wf",
            reportlets_dir=reportlets_dir,
            output_dir=output_dir,
            bids_dir=bids_dir,
            debug=debug,
            low_mem=low_mem,
            longitudinal=longitudinal,
            omp_nthreads=omp_nthreads,
            skull_strip_template=skull_strip_template,
            skull_strip_fixed_seed=skull_strip_fixed_seed,
            freesurfer=freesurfer,
            fs_spaces=fs_spaces,
            template=template,
            hires=hires,
        )

        single_subject_wf.config['execution']['crashdump_dir'] = (
            os.path.join(output_dir, "smriprep", "sub-" + subject_id, 'log', run_uuid)
        )
        for node in single_subject_wf._get_all_nodes():
            node.config = deepcopy(single_subject_wf.config)
        if freesurfer:
            smriprep_wf.connect(fsdir, 'subjects_dir',
                                single_subject_wf, 'inputnode.subjects_dir')
        else:
            smriprep_wf.add_nodes([single_subject_wf])

    return smriprep_wf


def init_single_subject_wf(subject_id, name, reportlets_dir, output_dir, bids_dir,
                           debug, low_mem, longitudinal, omp_nthreads,
                           skull_strip_template, skull_strip_fixed_seed,
                           freesurfer, fs_spaces, template, hires):
    """
    This workflow organizes the preprocessing pipeline for a single subject.
    It collects and reports information about the subject, and prepares
    sub-workflows to perform anatomical and functional preprocessing.

    Anatomical preprocessing is performed in a single workflow, regardless of
    the number of sessions.
    Functional preprocessing is performed using a separate workflow for each
    individual BOLD series.

    .. workflow::
        :graph2use: orig
        :simple_form: yes

        from smriprep.workflows.base import init_single_subject_wf
        wf = init_single_subject_wf(subject_id='test',
                                    task_id='',
                                    echo_idx=None,
                                    name='single_subject_wf',
                                    reportlets_dir='.',
                                    output_dir='.',
                                    bids_dir='.',
                                    ignore=[],
                                    debug=False,
                                    low_mem=False,
                                    anat_only=False,
                                    longitudinal=False,
                                    t2s_coreg=False,
                                    omp_nthreads=1,
                                    skull_strip_template='OASIS30ANTs',
                                    skull_strip_fixed_seed=False,
                                    freesurfer=True,
                                    template='MNI152NLin2009cAsym',
                                    fs_spaces=['T1w', 'fsnative',
                                                  'template', 'fsaverage5'],
                                    medial_surface_nan=False,
                                    cifti_output=False,
                                    hires=True,
                                    use_bbr=True,
                                    bold2t1w_dof=9,
                                    fmap_bspline=False,
                                    fmap_demean=True,
                                    use_syn=True,
                                    force_syn=True,
                                    use_aroma=False,
                                    aroma_melodic_dim=-200,
                                    ignore_aroma_err=False)

    Parameters

        subject_id : str
            List of subject labels
        task_id : str or None
            Task ID of BOLD series to preprocess, or ``None`` to preprocess all
        echo_idx : int or None
            Index of echo to preprocess in multiecho BOLD series,
            or ``None`` to preprocess all
        name : str
            Name of workflow
        ignore : list
            Preprocessing steps to skip (may include "slicetiming", "fieldmaps")
        debug : bool
            Enable debugging outputs
        low_mem : bool
            Write uncompressed .nii files in some cases to reduce memory usage
        anat_only : bool
            Disable functional workflows
        longitudinal : bool
            Treat multiple sessions as longitudinal (may increase runtime)
            See sub-workflows for specific differences
        t2s_coreg : bool
            For multi-echo EPI, use the calculated T2*-map for T2*-driven coregistration
        omp_nthreads : int
            Maximum number of threads an individual process may use
        skull_strip_template : str
            Name of ANTs skull-stripping template ('OASIS30ANTs' or 'NKI')
        skull_strip_fixed_seed : bool
            Do not use a random seed for skull-stripping - will ensure
            run-to-run replicability when used with --omp-nthreads 1
        reportlets_dir : str
            Directory in which to save reportlets
        output_dir : str
            Directory in which to save derivatives
        bids_dir : str
            Root directory of BIDS dataset
        freesurfer : bool
            Enable FreeSurfer surface reconstruction (may increase runtime)
        fs_spaces : list
            List of output spaces functional images are to be resampled to.
            Some parts of pipeline will only be instantiated for some output spaces.

            Valid spaces:

             - T1w
             - template
             - fsnative
             - fsaverage (or other pre-existing FreeSurfer templates)
        template : str
            Name of template targeted by ``template`` output space
        medial_surface_nan : bool
            Replace medial wall values with NaNs on functional GIFTI files
        cifti_output : bool
            Generate bold CIFTI file in output spaces
        hires : bool
            Enable sub-millimeter preprocessing in FreeSurfer
        use_bbr : bool or None
            Enable/disable boundary-based registration refinement.
            If ``None``, test BBR result for distortion before accepting.
        bold2t1w_dof : 6, 9 or 12
            Degrees-of-freedom for BOLD-T1w registration
        fmap_bspline : bool
            **Experimental**: Fit B-Spline field using least-squares
        fmap_demean : bool
            Demean voxel-shift map during unwarp
        use_syn : bool
            **Experimental**: Enable ANTs SyN-based susceptibility distortion correction (SDC).
            If fieldmaps are present and enabled, this is not run, by default.
        force_syn : bool
            **Temporary**: Always run SyN-based SDC
        use_aroma : bool
            Perform ICA-AROMA on MNI-resampled functional series
        ignore_aroma_err : bool
            Do not fail on ICA-AROMA errors

    Inputs

        subjects_dir
            FreeSurfer SUBJECTS_DIR

    """
    from ..interfaces.reports import AboutSummary, SubjectSummary
    if name in ('single_subject_wf', 'single_subject_smripreptest_wf'):
        # for documentation purposes
        subject_data = {
            't1w': ['/completely/made/up/path/sub-01_T1w.nii.gz'],
        }
    else:
        subject_data = collect_data(bids_dir, subject_id)[0]

    if not subject_data['t1w']:
        raise Exception("No T1w images found for participant {}. "
                        "All workflows require T1w images.".format(subject_id))

    workflow = Workflow(name=name)
    workflow.__desc__ = """
Results included in this manuscript come from preprocessing
performed using *sMRIPprep* {smriprep_ver}
(@fmriprep1; @fmriprep2; RRID:SCR_016216),
which is based on *Nipype* {nipype_ver}
(@nipype1; @nipype2; RRID:SCR_002502).

""".format(smriprep_ver=__version__, nipype_ver=nipype_ver)
    workflow.__postdesc__ = """

For more details of the pipeline, see [the section corresponding
to workflows in *sMRIPrep*'s documentation]\
(https://smriprep.readthedocs.io/en/latest/workflows.html \
"sMRIPrep's documentation").


### References

"""

    inputnode = pe.Node(niu.IdentityInterface(fields=['subjects_dir']),
                        name='inputnode')

    bidssrc = pe.Node(BIDSDataGrabber(subject_data=subject_data, anat_only=True),
                      name='bidssrc')

    bids_info = pe.Node(BIDSInfo(), name='bids_info', run_without_submitting=True)

    summary = pe.Node(SubjectSummary(fs_spaces=fs_spaces, template=template),
                      name='summary', run_without_submitting=True)

    about = pe.Node(AboutSummary(version=__version__,
                                 command=' '.join(sys.argv)),
                    name='about', run_without_submitting=True)

    ds_report_summary = pe.Node(
        DerivativesDataSink(base_directory=reportlets_dir,
                            suffix='summary'),
        name='ds_report_summary', run_without_submitting=True)

    ds_report_about = pe.Node(
        DerivativesDataSink(base_directory=reportlets_dir,
                            suffix='about'),
        name='ds_report_about', run_without_submitting=True)

    # Preprocessing of T1w (includes registration to MNI)
    anat_preproc_wf = init_anat_preproc_wf(name="anat_preproc_wf",
                                           skull_strip_template=skull_strip_template,
                                           skull_strip_fixed_seed=skull_strip_fixed_seed,
                                           fs_spaces=fs_spaces,
                                           template=template,
                                           debug=debug,
                                           longitudinal=longitudinal,
                                           omp_nthreads=omp_nthreads,
                                           freesurfer=freesurfer,
                                           hires=hires,
                                           reportlets_dir=reportlets_dir,
                                           output_dir=output_dir,
                                           num_t1w=len(subject_data['t1w']))

    workflow.connect([
        (inputnode, anat_preproc_wf, [('subjects_dir', 'inputnode.subjects_dir')]),
        (bidssrc, bids_info, [(('t1w', fix_multi_T1w_source_name), 'in_file')]),
        (inputnode, summary, [('subjects_dir', 'subjects_dir')]),
        (bidssrc, summary, [('t1w', 't1w'),
                            ('t2w', 't2w')]),
        (bids_info, summary, [('subject_id', 'subject_id')]),
        (bidssrc, anat_preproc_wf, [('t1w', 'inputnode.t1w'),
                                    ('t2w', 'inputnode.t2w'),
                                    ('roi', 'inputnode.roi'),
                                    ('flair', 'inputnode.flair')]),
        (summary, anat_preproc_wf, [('subject_id', 'inputnode.subject_id')]),
        (bidssrc, ds_report_summary, [(('t1w', fix_multi_T1w_source_name), 'source_file')]),
        (summary, ds_report_summary, [('out_report', 'in_file')]),
        (bidssrc, ds_report_about, [(('t1w', fix_multi_T1w_source_name), 'source_file')]),
        (about, ds_report_about, [('out_report', 'in_file')]),
    ])

    return workflow

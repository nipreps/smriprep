#!/usr/bin/env python
# -*- coding: utf-8 -*-
# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
"""
sMRIPrep base processing workflows
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


def init_smriprep_wf(
    debug,
    freesurfer,
    hires,
    layout,
    longitudinal,
    low_mem,
    omp_nthreads,
    output_dir,
    output_spaces,
    run_uuid,
    skull_strip_fixed_seed,
    skull_strip_template,
    subject_list,
    work_dir,
):
    """
    This workflow organizes the execution of sMRIPrep, with a sub-workflow for
    each subject.

    If FreeSurfer's recon-all is to be run, a FreeSurfer derivatives folder is
    created and populated with any needed template subjects.

    .. workflow::
        :graph2use: orig
        :simple_form: yes

        import os
        from pybids import BIDSLayout
        os.environ['FREESURFER_HOME'] = os.getcwd()
        from smriprep.workflows.base import init_smriprep_wf
        wf = init_smriprep_wf(
            debug=False,
            freesurfer=True,
            hires=True,
            layout=BIDSLayout('.', validate=False),
            longitudinal=False,
            low_mem=False,
            omp_nthreads=1,
            output_dir='.',
            output_spaces={'MNI152NLin2009cAsym': {}, 'fsnative': {}, 'fsaverage5': {}},
            run_uuid='testrun',
            skull_strip_fixed_seed=False,
            skull_strip_template='OASIS30ANTs',
            subject_list=['smripreptest'],
            work_dir='.',
        )

    Parameters

        debug : bool
            Enable debugging outputs
        freesurfer : bool
            Enable FreeSurfer surface reconstruction (may increase runtime)
        hires : bool
            Enable sub-millimeter preprocessing in FreeSurfer
        layout : BIDSLayout object
            BIDS dataset layout
        longitudinal : bool
            Treat multiple sessions as longitudinal (may increase runtime)
            See sub-workflows for specific differences
        low_mem : bool
            Write uncompressed .nii files in some cases to reduce memory usage
        omp_nthreads : int
            Maximum number of threads an individual process may use
        output_dir : str
            Directory in which to save derivatives
        output_spaces : list
            List of spatial normalization targets. Some parts of pipeline will
            only be instantiated for some output spaces. Valid spaces:
              - Any template identifier from TemplateFlow
              - Path to a template folder organized following TemplateFlow's conventions
        run_uuid : str
            Unique identifier for execution instance
        skull_strip_fixed_seed : bool
            Do not use a random seed for skull-stripping - will ensure
            run-to-run replicability when used with --omp-nthreads 1
        skull_strip_template : str
            Name of ANTs skull-stripping template ('OASIS30ANTs' or 'NKI')
        subject_list : list
            List of subject labels
        work_dir : str
            Directory in which to store workflow execution state and temporary files

    """
    smriprep_wf = Workflow(name='smriprep_wf')
    smriprep_wf.base_dir = work_dir

    if freesurfer:
        fsdir = pe.Node(
            BIDSFreeSurferDir(
                derivatives=output_dir,
                freesurfer_home=os.getenv('FREESURFER_HOME'),
                spaces=[s for s in output_spaces.keys() if s.startswith('fsaverage')] + [
                    'fsnative'] * ('fsnative' in output_spaces)),
            name='fsdir_run_%s' % run_uuid.replace('-', '_'), run_without_submitting=True)

    reportlets_dir = os.path.join(work_dir, 'reportlets')
    for subject_id in subject_list:
        single_subject_wf = init_single_subject_wf(
            debug=debug,
            freesurfer=freesurfer,
            hires=hires,
            layout=layout,
            longitudinal=longitudinal,
            low_mem=low_mem,
            name="single_subject_%s_wf" % subject_id,
            omp_nthreads=omp_nthreads,
            output_dir=output_dir,
            output_spaces=output_spaces,
            reportlets_dir=reportlets_dir,
            skull_strip_fixed_seed=skull_strip_fixed_seed,
            skull_strip_template=skull_strip_template,
            subject_id=subject_id,
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


def init_single_subject_wf(
    debug,
    freesurfer,
    hires,
    layout,
    longitudinal,
    low_mem,
    name,
    omp_nthreads,
    output_dir,
    output_spaces,
    reportlets_dir,
    skull_strip_fixed_seed,
    skull_strip_template,
    subject_id,
):
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
        from bids import BIDSLayout
        wf = init_single_subject_wf(
            debug=False,
            freesurfer=True,
            hires=True,
            layout=BIDSLayout('.', validate=False),
            longitudinal=False,
            low_mem=False,
            name='single_subject_wf',
            omp_nthreads=1,
            output_dir='.',
            output_spaces={'MNI152NLin2009cAsym': {}, 'fsnative': {}, 'fsaverage5': {}},
            reportlets_dir='.',
            skull_strip_fixed_seed=False,
            skull_strip_template='OASIS30ANTs,
            subject_id='test',
        )


    Parameters

        debug : bool
            Enable debugging outputs
        freesurfer : bool
            Enable FreeSurfer surface reconstruction (may increase runtime)
        hires : bool
            Enable sub-millimeter preprocessing in FreeSurfer
        layout : BIDSLayout object
            BIDS dataset layout
        longitudinal : bool
            Treat multiple sessions as longitudinal (may increase runtime)
            See sub-workflows for specific differences
        low_mem : bool
            Write uncompressed .nii files in some cases to reduce memory usage
        name : str
            Name of workflow
        omp_nthreads : int
            Maximum number of threads an individual process may use
        output_dir : str
            Directory in which to save derivatives
        output_spaces : list
            List of spatial normalization targets. Some parts of pipeline will
            only be instantiated for some output spaces. Valid spaces:
              - Any template identifier from TemplateFlow
              - Path to a template folder organized following TemplateFlow's conventions
        reportlets_dir : str
            Directory in which to save reportlets
        skull_strip_fixed_seed : bool
            Do not use a random seed for skull-stripping - will ensure
            run-to-run replicability when used with --omp-nthreads 1
        skull_strip_template : str
            Name of ANTs skull-stripping template ('OASIS30ANTs' or 'NKI')
        subject_id : str
            List of subject labels

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
        subject_data = collect_data(layout, subject_id)[0]

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

    bids_info = pe.Node(BIDSInfo(bids_dir=layout.root), name='bids_info',
                        run_without_submitting=True)

    summary = pe.Node(SubjectSummary(output_spaces=list(output_spaces.keys())),
                      name='summary', run_without_submitting=True)

    about = pe.Node(AboutSummary(version=__version__,
                                 command=' '.join(sys.argv)),
                    name='about', run_without_submitting=True)

    ds_report_summary = pe.Node(
        DerivativesDataSink(base_directory=reportlets_dir,
                            desc='summary', keep_dtype=True),
        name='ds_report_summary', run_without_submitting=True)

    ds_report_about = pe.Node(
        DerivativesDataSink(base_directory=reportlets_dir,
                            desc='about', keep_dtype=True),
        name='ds_report_about', run_without_submitting=True)

    # Preprocessing of T1w (includes registration to MNI)
    anat_preproc_wf = init_anat_preproc_wf(
        bids_root=layout.root,
        debug=debug,
        freesurfer=freesurfer,
        hires=hires,
        longitudinal=longitudinal,
        name="anat_preproc_wf",
        num_t1w=len(subject_data['t1w']),
        omp_nthreads=omp_nthreads,
        output_dir=output_dir,
        output_spaces=output_spaces,
        reportlets_dir=reportlets_dir,
        skull_strip_fixed_seed=skull_strip_fixed_seed,
        skull_strip_template=skull_strip_template,
    )

    workflow.connect([
        (inputnode, anat_preproc_wf, [('subjects_dir', 'inputnode.subjects_dir')]),
        (bidssrc, bids_info, [(('t1w', fix_multi_T1w_source_name), 'in_file')]),
        (inputnode, summary, [('subjects_dir', 'subjects_dir')]),
        (bidssrc, summary, [('t1w', 't1w'),
                            ('t2w', 't2w')]),
        (bids_info, summary, [('subject', 'subject_id')]),
        (bids_info, anat_preproc_wf, [(('subject', _prefix), 'inputnode.subject_id')]),
        (bidssrc, anat_preproc_wf, [('t1w', 'inputnode.t1w'),
                                    ('t2w', 'inputnode.t2w'),
                                    ('roi', 'inputnode.roi'),
                                    ('flair', 'inputnode.flair')]),
        (bidssrc, ds_report_summary, [(('t1w', fix_multi_T1w_source_name), 'source_file')]),
        (summary, ds_report_summary, [('out_report', 'in_file')]),
        (bidssrc, ds_report_about, [(('t1w', fix_multi_T1w_source_name), 'source_file')]),
        (about, ds_report_about, [('out_report', 'in_file')]),
    ])

    return workflow


def _prefix(subid):
    if subid.startswith('sub-'):
        return subid
    return '-'.join(('sub', subid))

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
"""*sMRIPrep* base processing workflows."""

import os
import sys
from copy import deepcopy

from nipype import __version__ as nipype_ver
from nipype.interfaces import utility as niu
from nipype.pipeline import engine as pe
from niworkflows.engine.workflows import LiterateWorkflow as Workflow
from niworkflows.interfaces.bids import BIDSDataGrabber, BIDSFreeSurferDir, BIDSInfo
from niworkflows.utils.bids import collect_data
from niworkflows.utils.misc import fix_multi_T1w_source_name

from ..__about__ import __version__
from ..interfaces import DerivativesDataSink
from .anatomical import init_anat_preproc_wf


def init_smriprep_wf(
    *,
    sloppy,
    debug,
    derivatives,
    freesurfer,
    fs_subjects_dir,
    hires,
    fs_no_resume,
    layout,
    longitudinal,
    low_mem,
    msm_sulc,
    omp_nthreads,
    output_dir,
    run_uuid,
    skull_strip_mode,
    skull_strip_fixed_seed,
    skull_strip_template,
    spaces,
    subject_list,
    work_dir,
    bids_filters,
    cifti_output,
):
    """
    Create the execution graph of *sMRIPrep*, with a sub-workflow for each subject.

    If FreeSurfer's ``recon-all`` is to be run, a FreeSurfer derivatives folder is
    created and populated with any needed template subjects.

    Workflow Graph
        .. workflow::
            :graph2use: orig
            :simple_form: yes

            import os
            from collections import namedtuple
            BIDSLayout = namedtuple('BIDSLayout', ['root'])
            os.environ['FREESURFER_HOME'] = os.getcwd()
            from smriprep.workflows.base import init_smriprep_wf
            from niworkflows.utils.spaces import SpatialReferences, Reference
            spaces = SpatialReferences(spaces=['MNI152NLin2009cAsym', 'fsaverage5'])
            spaces.checkpoint()
            wf = init_smriprep_wf(
                sloppy=False,
                debug=False,
                derivatives=[],
                freesurfer=True,
                fs_subjects_dir=None,
                hires=True,
                fs_no_resume=False,
                layout=BIDSLayout('.'),
                longitudinal=False,
                low_mem=False,
                msm_sulc=False,
                omp_nthreads=1,
                output_dir='.',
                run_uuid='testrun',
                skull_strip_fixed_seed=False,
                skull_strip_mode='force',
                skull_strip_template=Reference('OASIS30ANTs'),
                spaces=spaces,
                subject_list=['smripreptest'],
                work_dir='.',
                bids_filters=None,
                cifti_output=None,
            )

    Parameters
    ----------
    sloppy: :obj:`bool`
        Quick, impercise operations. Used to decrease workflow duration.
    debug : :obj:`bool`
        Enable debugging outputs
    derivatives : :obj:`list` of directories
        Fast-track the workflow by searching for existing derivatives.
    freesurfer : :obj:`bool`
        Enable FreeSurfer surface reconstruction (may increase runtime)
    fs_subjects_dir : os.PathLike or None
        Use existing FreeSurfer subjects directory if provided
    hires : :obj:`bool`
        Enable sub-millimeter preprocessing in FreeSurfer
    layout : BIDSLayout object
        BIDS dataset layout
    longitudinal : :obj:`bool`
        Treat multiple sessions as longitudinal (may increase runtime)
        See sub-workflows for specific differences
    low_mem : :obj:`bool`
        Write uncompressed .nii files in some cases to reduce memory usage
    msm_sulc : :obj:`bool`
        Run Multimodal Surface Matching with sulcal depth maps
    omp_nthreads : :obj:`int`
        Maximum number of threads an individual process may use
    output_dir : :obj:`str`
        Directory in which to save derivatives
    run_uuid : :obj:`str`
        Unique identifier for execution instance
    skull_strip_fixed_seed : :obj:`bool`
        Do not use a random seed for skull-stripping - will ensure
        run-to-run replicability when used with --omp-nthreads 1
    skull_strip_mode : :obj:`str`
        Determiner for T1-weighted skull stripping (`force` ensures skull stripping,
        `skip` ignores skull stripping, and `auto` automatically ignores skull stripping
        if pre-stripped brains are detected).
    skull_strip_template : :py:class:`~niworkflows.utils.spaces.Reference`
        Spatial reference to use in atlas-based brain extraction.
    spaces : :py:class:`~niworkflows.utils.spaces.SpatialReferences`
        Object containing standard and nonstandard space specifications.
    subject_list : :obj:`list`
        List of subject labels
    work_dir : :obj:`str`
        Directory in which to store workflow execution state and
        temporary files
    bids_filters : dict
        Provides finer specification of the pipeline input files through pybids entities filters.
        A dict with the following structure {<suffix>:{<entity>:<filter>,...},...}

    """
    smriprep_wf = Workflow(name='smriprep_wf')
    smriprep_wf.base_dir = work_dir

    if freesurfer:
        fsdir = pe.Node(
            BIDSFreeSurferDir(
                derivatives=output_dir,
                freesurfer_home=os.getenv('FREESURFER_HOME'),
                spaces=spaces.get_fs_spaces(),
            ),
            name='fsdir_run_{}'.format(run_uuid.replace('-', '_')),
            run_without_submitting=True,
        )
        if fs_subjects_dir is not None:
            fsdir.inputs.subjects_dir = str(fs_subjects_dir.absolute())

    for subject_id in subject_list:
        single_subject_wf = init_single_subject_wf(
            sloppy=sloppy,
            debug=debug,
            freesurfer=freesurfer,
            derivatives=derivatives,
            hires=hires,
            fs_no_resume=fs_no_resume,
            layout=layout,
            longitudinal=longitudinal,
            low_mem=low_mem,
            msm_sulc=msm_sulc,
            name=f'single_subject_{subject_id}_wf',
            omp_nthreads=omp_nthreads,
            output_dir=output_dir,
            skull_strip_fixed_seed=skull_strip_fixed_seed,
            skull_strip_mode=skull_strip_mode,
            skull_strip_template=skull_strip_template,
            spaces=spaces,
            subject_id=subject_id,
            bids_filters=bids_filters,
            cifti_output=cifti_output,
        )

        single_subject_wf.config['execution']['crashdump_dir'] = os.path.join(
            output_dir, 'smriprep', 'sub-' + subject_id, 'log', run_uuid
        )
        for node in single_subject_wf._get_all_nodes():
            node.config = deepcopy(single_subject_wf.config)
        if freesurfer:
            smriprep_wf.connect(fsdir, 'subjects_dir', single_subject_wf, 'inputnode.subjects_dir')
        else:
            smriprep_wf.add_nodes([single_subject_wf])

    return smriprep_wf


def init_single_subject_wf(
    *,
    sloppy,
    debug,
    derivatives,
    freesurfer,
    hires,
    fs_no_resume,
    layout,
    longitudinal,
    low_mem,
    msm_sulc,
    name,
    omp_nthreads,
    output_dir,
    skull_strip_fixed_seed,
    skull_strip_mode,
    skull_strip_template,
    spaces,
    subject_id,
    bids_filters,
    cifti_output,
):
    """
    Create a single subject workflow.

    This workflow organizes the preprocessing pipeline for a single subject.
    It collects and reports information about the subject, and prepares
    sub-workflows to perform anatomical and functional preprocessing.

    Anatomical preprocessing is performed in a single workflow, regardless of
    the number of sessions.
    Functional preprocessing is performed using a separate workflow for each
    individual BOLD series.

    Workflow Graph
        .. workflow::
            :graph2use: orig
            :simple_form: yes

            from collections import namedtuple
            from niworkflows.utils.spaces import SpatialReferences, Reference
            from smriprep.workflows.base import init_single_subject_wf
            BIDSLayout = namedtuple('BIDSLayout', ['root'])
            spaces = SpatialReferences(spaces=['MNI152NLin2009cAsym', 'fsaverage5'])
            spaces.checkpoint()
            wf = init_single_subject_wf(
                sloppy=False,
                debug=False,
                freesurfer=True,
                derivatives=[],
                hires=True,
                fs_no_resume=False,
                layout=BIDSLayout('.'),
                longitudinal=False,
                low_mem=False,
                msm_sulc=False,
                name='single_subject_wf',
                omp_nthreads=1,
                output_dir='.',
                skull_strip_fixed_seed=False,
                skull_strip_mode='force',
                skull_strip_template=Reference('OASIS30ANTs'),
                spaces=spaces,
                subject_id='test',
                bids_filters=None,
                cifti_output=None,
            )

    Parameters
    ----------
    sloppy: :obj:`bool`
        Quick, impercise operations. Used to decrease workflow duration.
    debug : :obj:`bool`
        Enable debugging outputs
    derivatives : :obj:`list` of directories
        Fast-track the workflow by searching for existing derivatives.
    freesurfer : :obj:`bool`
        Enable FreeSurfer surface reconstruction (may increase runtime)
    hires : :obj:`bool`
        Enable sub-millimeter preprocessing in FreeSurfer
    fs_no_resume : bool
        Adjust pipeline to reuse base template
        of an existing longitudinal freesurfer output
    layout : BIDSLayout object
        BIDS dataset layout
    longitudinal : :obj:`bool`
        Treat multiple sessions as longitudinal (may increase runtime)
        See sub-workflows for specific differences
    low_mem : :obj:`bool`
        Write uncompressed .nii files in some cases to reduce memory usage
    name : :obj:`str`
        Name of workflow
    omp_nthreads : :obj:`int`
        Maximum number of threads an individual process may use
    output_dir : :obj:`str`
        Directory in which to save derivatives
    skull_strip_fixed_seed : :obj:`bool`
        Do not use a random seed for skull-stripping - will ensure
        run-to-run replicability when used with --omp-nthreads 1
    skull_strip_mode : :obj:`str`
        Determiner for T1-weighted skull stripping (`force` ensures skull stripping,
        `skip` ignores skull stripping, and `auto` automatically ignores skull stripping
        if pre-stripped brains are detected).
    skull_strip_template : :py:class:`~niworkflows.utils.spaces.Reference`
        Spatial reference to use in atlas-based brain extraction.
    spaces : :py:class:`~niworkflows.utils.spaces.SpatialReferences`
        Object containing standard and nonstandard space specifications.
    subject_id : :obj:`str`
        List of subject labels
    bids_filters : dict
        Provides finer specification of the pipeline input files through pybids entities filters.
        A dict with the following structure {<suffix>:{<entity>:<filter>,...},...}

    Inputs
    ------
    subjects_dir
        FreeSurfer SUBJECTS_DIR

    """
    from ..interfaces.reports import AboutSummary, SubjectSummary

    if name in ('single_subject_wf', 'single_subject_smripreptest_wf'):
        # for documentation purposes
        subject_data = {
            't1w': ['/completely/made/up/path/sub-01_T1w.nii.gz'],
            't2w': [],
            'flair': [],
        }
    else:
        subject_data = collect_data(layout, subject_id, bids_filters=bids_filters)[0]

    if not subject_data['t1w']:
        raise Exception(
            f'No T1w images found for participant {subject_id}. All workflows require T1w images.'
        )

    workflow = Workflow(name=name)
    workflow.__desc__ = f"""
Results included in this manuscript come from preprocessing
performed using *sMRIPprep* {__version__}
(@fmriprep1; @fmriprep2; RRID:SCR_016216),
which is based on *Nipype* {nipype_ver}
(@nipype1; @nipype2; RRID:SCR_002502).

"""
    workflow.__postdesc__ = """

For more details of the pipeline, see [the section corresponding
to workflows in *sMRIPrep*'s documentation]\
(https://smriprep.readthedocs.io/en/latest/workflows.html \
"sMRIPrep's documentation").


### References

"""

    from ..utils.bids import collect_derivatives

    deriv_cache = {}
    std_spaces = spaces.get_spaces(nonstandard=False, dim=(3,))
    std_spaces.append('fsnative')
    for deriv_dir in derivatives:
        deriv_cache.update(collect_derivatives(deriv_dir, subject_id, std_spaces))

    inputnode = pe.Node(niu.IdentityInterface(fields=['subjects_dir']), name='inputnode')

    bidssrc = pe.Node(BIDSDataGrabber(subject_data=subject_data, anat_only=True), name='bidssrc')

    bids_info = pe.Node(
        BIDSInfo(bids_dir=layout.root), name='bids_info', run_without_submitting=True
    )

    summary = pe.Node(
        SubjectSummary(output_spaces=spaces.get_spaces(nonstandard=False)),
        name='summary',
        run_without_submitting=True,
    )

    about = pe.Node(
        AboutSummary(version=__version__, command=' '.join(sys.argv)),
        name='about',
        run_without_submitting=True,
    )

    ds_report_summary = pe.Node(
        DerivativesDataSink(
            base_directory=output_dir,
            dismiss_entities=('session',),
            desc='summary',
            datatype='figures',
        ),
        name='ds_report_summary',
        run_without_submitting=True,
    )

    ds_report_about = pe.Node(
        DerivativesDataSink(
            base_directory=output_dir,
            dismiss_entities=('session',),
            desc='about',
            datatype='figures',
        ),
        name='ds_report_about',
        run_without_submitting=True,
    )

    # Preprocessing of T1w (includes registration to MNI)
    anat_preproc_wf = init_anat_preproc_wf(
        bids_root=layout.root,
        layout=layout,
        sloppy=sloppy,
        debug=debug,
        precomputed=deriv_cache,
        freesurfer=freesurfer,
        hires=hires,
        fs_no_resume=fs_no_resume,
        longitudinal=longitudinal,
        msm_sulc=msm_sulc,
        name='anat_preproc_wf',
        t1w=subject_data['t1w'],
        t2w=subject_data['t2w'],
        flair=subject_data['flair'],
        omp_nthreads=omp_nthreads,
        output_dir=output_dir,
        skull_strip_fixed_seed=skull_strip_fixed_seed,
        skull_strip_mode=skull_strip_mode,
        skull_strip_template=skull_strip_template,
        spaces=spaces,
        cifti_output=cifti_output,
    )

    # fmt:off
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
    # fmt:on

    return workflow


def _prefix(subid):
    if subid.startswith('sub-'):
        return subid
    return '-'.join(('sub', subid))

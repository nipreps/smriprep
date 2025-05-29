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
"""sMRIPrep: Structural MRI PREProcessing workflow."""


def main():
    """Set an entrypoint."""
    opts = get_parser().parse_args()
    if opts.longitudinal:
        opts.subject_anatomical_reference = 'unbiased'
        print(
            'The "--longitudinal" flag is deprecated. Use '
            '"--subject-anatomical-reference unbiased" instead.'
        )

    if opts.subject_anatomical_reference == 'unbiased':
        opts['longitudinal'] = True
    return build_opts(opts)


def check_deps(workflow):
    """Make sure all dependencies are installed."""
    from nipype.utils.filemanip import which

    return sorted(
        (node.interface.__class__.__name__, node.interface._cmd)
        for node in workflow._get_all_nodes()
        if (hasattr(node.interface, '_cmd') and which(node.interface._cmd.split()[0]) is None)
    )


def get_parser():
    """Build parser object."""
    from argparse import ArgumentParser, RawTextHelpFormatter
    from pathlib import Path

    from niworkflows.utils.spaces import (
        OutputReferencesAction,
        Reference,
        SpatialReferences,
    )

    import smriprep

    def _drop_ses(value):
        return value.removeprefix('ses-')

    parser = ArgumentParser(
        description='sMRIPrep: Structural MRI PREProcessing workflows',
        formatter_class=RawTextHelpFormatter,
    )

    # Arguments as specified by BIDS-Apps
    # required, positional arguments
    # IMPORTANT: they must go directly with the parser object
    parser.add_argument(
        'bids_dir',
        action='store',
        type=Path,
        help='the root folder of a BIDS valid dataset (sub-XXXXX folders should '
        'be found at the top level in this folder).',
    )
    parser.add_argument(
        'output_dir',
        action='store',
        type=Path,
        help='the output path for the outcomes of preprocessing and visual reports',
    )
    parser.add_argument(
        'analysis_level',
        choices=['participant'],
        help='processing stage to be run, only "participant" in the case of '
        'sMRIPrep (see BIDS-Apps specification).',
    )

    # optional arguments
    parser.add_argument(
        '--version',
        action='version',
        version=f'smriprep v{smriprep.__version__}',
    )

    g_bids = parser.add_argument_group('Options for filtering BIDS queries')
    g_bids.add_argument(
        '--participant-label',
        '--participant_label',
        action='store',
        nargs='+',
        help='a space delimited list of participant identifiers or a single '
        'identifier (the sub- prefix can be removed)',
    )
    g_bids.add_argument(
        '--session-label',
        nargs='+',
        type=_drop_ses,
        help='A space delimited list of session identifiers or a single '
        'identifier (the ses- prefix can be removed)',
    )
    g_bids.add_argument(
        '-d',
        '--derivatives',
        action='store',
        metavar='PATH',
        type=Path,
        nargs='*',
        help='Search PATH(s) for pre-computed derivatives.',
    )
    g_bids.add_argument(
        '--bids-filter-file',
        action='store',
        type=Path,
        metavar='PATH',
        help='a JSON file describing custom BIDS input filters using pybids '
        '{<suffix>:{<entity>:<filter>,...},...} '
        '(https://github.com/bids-standard/pybids/blob/master/bids/layout/config/bids.json)',
    )
    g_bids.add_argument(
        '--subject-anatomical-reference',
        choices=['first-alpha', 'unbiased', 'sessionwise'],
        default='first',
        help='Method to produce the reference anatomical space:'
        '\t"first-alpha" will use the first alphabetically sorted image'
        '\t"unbiased" will construct an unbiased template from all images '
        '(previously "--longitudinal")'
        '\t"sessionwise" will independently process each session. If multiple runs are '
        'found, the behavior will be similar to "first-alpha"',
    )

    g_perfm = parser.add_argument_group('Options to handle performance')
    g_perfm.add_argument(
        '--nprocs',
        '--ncpus',
        '--nthreads',
        '--n_cpus',
        '-n-cpus',
        action='store',
        type=int,
        help='number of CPUs to be used.',
    )
    g_perfm.add_argument(
        '--omp-nthreads',
        action='store',
        type=int,
        default=0,
        help='maximum number of threads per-process',
    )
    g_perfm.add_argument(
        '--mem-gb',
        '--mem_gb',
        action='store',
        default=0,
        type=float,
        help='upper bound memory limit for sMRIPrep processes (in GB).',
    )
    g_perfm.add_argument(
        '--low-mem',
        action='store_true',
        help='attempt to reduce memory usage (will increase disk usage in working directory)',
    )
    g_perfm.add_argument(
        '--use-plugin',
        action='store',
        default=None,
        help='nipype plugin configuration file',
    )
    g_perfm.add_argument('--boilerplate', action='store_true', help='generate boilerplate only')
    g_perfm.add_argument(
        '-v',
        '--verbose',
        dest='verbose_count',
        action='count',
        default=0,
        help='increases log verbosity for each occurrence, debug level is -vvv',
    )

    g_conf = parser.add_argument_group('Workflow configuration')
    g_conf.add_argument(
        '--output-spaces',
        nargs='*',
        action=OutputReferencesAction,
        default=SpatialReferences(),
        help='paths or keywords prescribing output spaces - '
        'standard spaces will be extracted for spatial normalization.',
    )
    g_conf.add_argument(
        '--longitudinal',
        action='store_true',
        help='DEPRECATED: use "--subject-anatomical-reference unbiased" instead',
    )

    #  ANTs options
    g_ants = parser.add_argument_group('Specific options for ANTs registrations')
    g_ants.add_argument(
        '--skull-strip-template',
        default='OASIS30ANTs',
        type=Reference.from_string,
        help='select a template for skull-stripping with antsBrainExtraction',
    )
    g_ants.add_argument(
        '--skull-strip-fixed-seed',
        action='store_true',
        help='do not use a random seed for skull-stripping - will ensure '
        'run-to-run replicability when used with --omp-nthreads 1',
    )
    g_ants.add_argument(
        '--skull-strip-mode',
        action='store',
        choices=('auto', 'skip', 'force'),
        default='auto',
        help='determiner for T1-weighted skull stripping (force ensures skull '
        'stripping, skip ignores skull stripping, and auto automatically '
        'ignores skull stripping if pre-stripped brains are detected).',
    )

    # FreeSurfer options
    g_fs = parser.add_argument_group('Specific options for FreeSurfer preprocessing')
    g_fs.add_argument(
        '--fs-license-file',
        metavar='PATH',
        type=Path,
        help='Path to FreeSurfer license key file. Get it (for free) by registering'
        ' at https://surfer.nmr.mgh.harvard.edu/registration.html',
    )
    g_fs.add_argument(
        '--fs-subjects-dir',
        metavar='PATH',
        type=Path,
        help='Path to existing FreeSurfer subjects directory to reuse. '
        '(default: OUTPUT_DIR/freesurfer)',
    )
    g_fs.add_argument(
        '--fs-no-resume',
        action='store_true',
        dest='fs_no_resume',
        help='EXPERT: Import pre-computed FreeSurfer reconstruction without resuming. '
        'The user is responsible for ensuring that all necessary files are present.',
    )
    g_fs.add_argument(
        '--cifti-output',
        nargs='?',
        const='91k',
        default=False,
        choices=('91k', '170k'),
        type=str,
        help='Output morphometry as CIFTI dense scalars. '
        'Optionally, the number of grayordinate can be specified '
        '(default is 91k, which equates to 2mm resolution)',
    )

    # Surface generation xor
    g_surfs = parser.add_argument_group('Surface preprocessing options')
    g_surfs.add_argument(
        '--no-submm-recon',
        action='store_false',
        dest='hires',
        help='disable sub-millimeter (hires) reconstruction',
    )
    g_surfs.add_argument(
        '--no-msm',
        action='store_false',
        dest='msm_sulc',
        help='Disable Multimodal Surface Matching surface registration.',
    )
    g_surfs_xor = g_surfs.add_mutually_exclusive_group()

    g_surfs_xor.add_argument(
        '--fs-no-reconall',
        action='store_false',
        dest='run_reconall',
        help='disable FreeSurfer surface preprocessing.',
    )

    g_other = parser.add_argument_group('Other options')
    g_other.add_argument(
        '-w',
        '--work-dir',
        action='store',
        type=Path,
        default=Path('work'),
        help='path where intermediate results should be stored',
    )
    g_other.add_argument(
        '--fast-track',
        action='store_true',
        default=False,
        help='fast-track the workflow by searching for existing derivatives. '
        '(DEPRECATED for --derivatives).',
    )
    g_other.add_argument(
        '--resource-monitor',
        action='store_true',
        default=False,
        help="enable Nipype's resource monitoring to keep track of memory and CPU usage",
    )
    g_other.add_argument(
        '--reports-only',
        action='store_true',
        default=False,
        help="only generate reports, don't run workflows. This will only rerun report "
        'aggregation, not reportlet generation for specific nodes.',
    )
    g_other.add_argument(
        '--run-uuid',
        action='store',
        default=None,
        help='Specify UUID of previous run, to include error logs in report. '
        'No effect without --reports-only.',
    )
    g_other.add_argument(
        '--write-graph',
        action='store_true',
        default=False,
        help='Write workflow graph.',
    )
    g_other.add_argument(
        '--stop-on-first-crash',
        action='store_true',
        default=False,
        help='Force stopping on first crash, even if a work directory was specified.',
    )
    g_other.add_argument(
        '--notrack',
        action='store_true',
        default=False,
        help='Opt-out of sending tracking information of this run to '
        'the sMRIPrep developers. This information helps to '
        'improve sMRIPrep and provides an indicator of real '
        'world usage crucial for obtaining funding.',
    )
    g_other.add_argument(
        '--sloppy',
        action='store_true',
        default=False,
        help='Use low-quality tools for speed - TESTING ONLY',
    )

    return parser


def build_opts(opts):
    """Trigger a new process that builds the workflow graph, based on the input options."""
    import gc
    import logging
    import os
    import sys
    import warnings
    from multiprocessing import Manager, Process, set_start_method
    from pathlib import Path

    from nipype import logging as nlogging
    from niworkflows.utils.misc import check_valid_fs_license

    set_start_method('forkserver')

    logging.addLevelName(25, 'IMPORTANT')  # Add a new level between INFO and WARNING
    logging.addLevelName(15, 'VERBOSE')  # Add a new level between INFO and DEBUG
    logger = logging.getLogger('cli')

    def _warn_redirect(message, category, filename, lineno, file=None, line=None):
        logger.warning('Captured warning (%s): %s', category, message)

    warnings.showwarning = _warn_redirect

    # Precedence: --fs-license-file, $FS_LICENSE, default_license
    if opts.fs_license_file is not None:
        os.environ['FS_LICENSE'] = os.path.abspath(opts.fs_license_file)

    if not check_valid_fs_license():
        raise RuntimeError(
            'ERROR: a valid license file is required for FreeSurfer to run. '
            'sMRIPrep looked for an existing license file at several paths, in this '
            'order: 1) command line argument ``--fs-license-file``; 2) ``$FS_LICENSE`` '
            'environment variable; and 3) the ``$FREESURFER_HOME/license.txt`` path. '
            'Get it (for free) by registering at https://'
            'surfer.nmr.mgh.harvard.edu/registration.html'
        )

    # Retrieve logging level
    log_level = int(max(25 - 5 * opts.verbose_count, logging.DEBUG))
    # Set logging
    logger.setLevel(log_level)
    nlogging.getLogger('nipype.workflow').setLevel(log_level)
    nlogging.getLogger('nipype.interface').setLevel(log_level)
    nlogging.getLogger('nipype.utils').setLevel(log_level)

    errno = 0

    # Call build_workflow(opts, retval)
    with Manager() as mgr:
        retval = mgr.dict()
        p = Process(target=build_workflow, args=(opts, retval))
        p.start()
        p.join()

        if p.exitcode != 0:
            sys.exit(p.exitcode)

        smriprep_wf = retval['workflow']
        plugin_settings = retval['plugin_settings']
        bids_dir = retval['bids_dir']
        output_dir = retval['output_dir']
        subject_session_list = retval['subject_session_list']
        run_uuid = retval['run_uuid']
        retcode = retval['return_code']

    if smriprep_wf is None:
        sys.exit(1)

    if opts.write_graph:
        smriprep_wf.write_graph(graph2use='colored', format='svg', simple_form=True)

    if opts.reports_only:
        sys.exit(int(retcode > 0))

    if opts.boilerplate:
        sys.exit(int(retcode > 0))

    # Check workflow for missing commands
    missing = check_deps(smriprep_wf)
    if missing:
        print('Cannot run sMRIPrep. Missing dependencies:')
        for iface, cmd in missing:
            print(f'\t{cmd} (Interface: {iface})')
        sys.exit(2)

    # Clean up master process before running workflow, which may create forks
    gc.collect()
    try:
        smriprep_wf.run(**plugin_settings)
    except RuntimeError:
        errno = 1
    else:
        if opts.run_reconall:
            from niworkflows.utils.misc import _copy_any
            from templateflow import api

            dseg_tsv = str(
                api.get(
                    'fsaverage',
                    hemi=None,
                    atlas=None,
                    segmentation='aparc',
                    suffix='dseg',
                    extension=['.tsv'],
                )
            )
            _copy_any(dseg_tsv, str(Path(output_dir) / 'smriprep' / 'desc-aseg_dseg.tsv'))
            _copy_any(dseg_tsv, str(Path(output_dir) / 'smriprep' / 'desc-aparcaseg_dseg.tsv'))
        logger.log(25, 'sMRIPrep finished without errors')
    finally:
        from nireports.assembler.tools import generate_reports

        from ..utils.bids import write_bidsignore, write_derivative_description

        logger.log(
            25, 'Writing reports for participants: %s', _pprint_subses(subject_session_list)
        )
        # Generate reports phase
        smriprep_dir = Path(output_dir) / 'smriprep'
        errno += generate_reports(subject_session_list, smriprep_dir, run_uuid)
        write_derivative_description(bids_dir, smriprep_dir)
        write_bidsignore(smriprep_dir)
    sys.exit(int(errno > 0))


def build_workflow(opts, retval):
    """
    Create the Nipype Workflow that supports the whole execution graph, given the inputs.

    All the checks and the construction of the workflow are done
    inside this function that has pickleable inputs and output
    dictionary (``retval``) to allow isolation using a
    ``multiprocessing.Process`` that allows smriprep to enforce
    a hard-limited memory-scope.

    """
    import json
    import uuid
    import warnings
    from os import cpu_count
    from shutil import copyfile
    from subprocess import CalledProcessError, TimeoutExpired, check_call
    from time import strftime

    from bids.layout import BIDSLayout, Query
    from nipype import config as ncfg
    from nipype import logging
    from niworkflows.utils.bids import collect_participants

    import smriprep
    from smriprep.workflows.base import init_smriprep_wf

    logger = logging.getLogger('nipype.workflow')

    INIT_MSG = """
    Running sMRIPrep version {version}:
      * BIDS dataset path: {bids_dir}.
      * Participants & Sessions: {subject_session_list}.
      * Run identifier: {uuid}.

    {spaces}
    """.format

    # Set up some instrumental utilities
    run_uuid = '{}_{}'.format(strftime('%Y%m%d-%H%M%S'), uuid.uuid4())

    # First check that bids_dir looks like a BIDS folder
    bids_dir = opts.bids_dir.resolve()
    layout = BIDSLayout(str(bids_dir), validate=False)
    subject_list = collect_participants(layout, participant_label=opts.participant_label)
    session_list = opts.session_label or []

    subject_session_list = []
    for subject in subject_list:
        sessions = layout.get_sessions(
            scope='raw',
            subject=subject,
            session=session_list or Query.OPTIONAL,
            suffix=['T1w', 'T2w'],  # TODO: Track supported modalities globally
        )
        if not sessions:
            if opts.subject_anatomical_reference == 'sessionwise':
                logger.warning(
                    '--subject-anatomical-reference "sessionwise" was requested, but no sessions '
                    f'were found for subject {subject}.'
                )
            subject_session_list.append((subject, None))
            continue

        if opts.subject_anatomical_reference == 'sessionwise':
            for session in sessions:
                subject_session_list.append((subject, session))
        else:
            # This will use all sessions either found by layout or passed in via --session-id
            # MG: Should session names be concatenated into a label to preserve provenance?
            subject_session_list.append((subject, sessions))

    bids_filters = json.loads(opts.bids_filter_file.read_text()) if opts.bids_filter_file else None

    # Load base plugin_settings from file if --use-plugin
    if opts.use_plugin is not None:
        from yaml import safe_load as loadyml

        with open(opts.use_plugin) as f:
            plugin_settings = loadyml(f)
        plugin_settings.setdefault('plugin_args', {})
    else:
        # Defaults
        plugin_settings = {
            'plugin': 'MultiProc',
            'plugin_args': {
                'raise_insufficient': False,
                'maxtasksperchild': 1,
            },
        }

    # Resource management options
    # Note that we're making strong assumptions about valid plugin args
    # This may need to be revisited if people try to use batch plugins
    nprocs = plugin_settings['plugin_args'].get('n_procs')
    # Permit overriding plugin config with specific CLI options
    if nprocs is None or opts.nprocs is not None:
        nprocs = opts.nprocs
        if nprocs is None or nprocs < 1:
            nprocs = cpu_count()
        plugin_settings['plugin_args']['n_procs'] = nprocs

    if opts.mem_gb:
        plugin_settings['plugin_args']['memory_gb'] = opts.mem_gb

    omp_nthreads = opts.omp_nthreads
    if omp_nthreads == 0:
        omp_nthreads = min(nprocs - 1 if nprocs > 1 else cpu_count(), 8)

    if 1 < nprocs < omp_nthreads:
        logger.warning(
            'Per-process threads (--omp-nthreads=%d) exceed total '
            'available CPUs (--nprocs/--ncpus=%d)',
            omp_nthreads,
            nprocs,
        )

    # Set up directories
    output_dir = opts.output_dir.resolve()
    log_dir = output_dir / 'smriprep' / 'logs'
    work_dir = opts.work_dir.resolve()

    # Check and create output and working directories
    log_dir.mkdir(parents=True, exist_ok=True)
    work_dir.mkdir(parents=True, exist_ok=True)

    # Nipype config (logs and execution)
    ncfg.update_config(
        {
            'logging': {'log_directory': str(log_dir), 'log_to_file': True},
            'execution': {
                'crashdump_dir': str(log_dir),
                'crashfile_format': 'txt',
                'get_linked_libs': False,
                'stop_on_first_crash': opts.stop_on_first_crash,
            },
            'monitoring': {
                'enabled': opts.resource_monitor,
                'sample_frequency': '0.5',
                'summary_append': True,
            },
        }
    )

    if opts.resource_monitor:
        ncfg.enable_resource_monitor()

    retval['return_code'] = 0
    retval['plugin_settings'] = plugin_settings
    retval['bids_dir'] = str(bids_dir)
    retval['output_dir'] = str(output_dir)
    retval['work_dir'] = str(work_dir)
    retval['subject_session_list'] = subject_session_list
    retval['run_uuid'] = run_uuid
    retval['workflow'] = None

    # Called with reports only
    if opts.reports_only:
        from nireports.assembler.tools import generate_reports

        logger.log(
            25, 'Running --reports-only on participants %s', _pprint_subses(subject_session_list)
        )
        if opts.run_uuid is not None:
            run_uuid = opts.run_uuid

        smriprep_dir = output_dir / 'smriprep'
        retval['return_code'] = generate_reports(subject_session_list, smriprep_dir, run_uuid)
        return retval

    output_spaces = opts.output_spaces
    if not output_spaces.is_cached():
        output_spaces.checkpoint()

    logger.log(
        25,
        INIT_MSG(
            version=smriprep.__version__,
            bids_dir=bids_dir,
            subject_session_list=_pprint_subses(subject_session_list),
            uuid=run_uuid,
            spaces=output_spaces,
        ),
    )

    derivatives = opts.derivatives or []
    if opts.fast_track:
        # XXX Makes strong assumption of legacy layout
        smriprep_dir = str(output_dir / 'smriprep')
        warnings.warn(
            f'Received DEPRECATED --fast-track flag. Adding {smriprep_dir} to --derivatives list.'
            f'Received DEPRECATED --fast-track flag. Adding {smriprep_dir} to --derivatives list.',
            stacklevel=1,
        )
        derivatives.append(smriprep_dir)

    # Build main workflow
    retval['workflow'] = init_smriprep_wf(
        sloppy=opts.sloppy,
        debug=False,
        derivatives=derivatives,
        freesurfer=opts.run_reconall,
        fs_subjects_dir=opts.fs_subjects_dir,
        hires=opts.hires,
        fs_no_resume=opts.fs_no_resume,
        layout=layout,
        longitudinal=opts.longitudinal,
        low_mem=opts.low_mem,
        msm_sulc=opts.msm_sulc,
        omp_nthreads=omp_nthreads,
        output_dir=str(output_dir),
        run_uuid=run_uuid,
        skull_strip_fixed_seed=opts.skull_strip_fixed_seed,
        skull_strip_mode=opts.skull_strip_mode,
        skull_strip_template=opts.skull_strip_template[0],
        spaces=output_spaces,
        subject_session_list=subject_session_list,
        work_dir=str(work_dir),
        bids_filters=bids_filters,
        cifti_output=opts.cifti_output,
    )
    retval['return_code'] = 0

    boilerplate = retval['workflow'].visit_desc()
    (log_dir / 'CITATION.md').write_text(boilerplate)
    logger.log(
        25,
        'Works derived from this sMRIPrep execution should '
        'include the following boilerplate:\n\n%s',
        boilerplate,
    )

    boilerplate_bib = smriprep.load_data('boilerplate.bib')

    # Generate HTML file resolving citations
    cmd = [
        'pandoc',
        '-s',
        '--bibliography',
        str(boilerplate_bib),
        '--citeproc',
        '--metadata',
        'pagetitle="sMRIPrep citation boilerplate"',
        str(log_dir / 'CITATION.md'),
        '-o',
        str(log_dir / 'CITATION.html'),
    ]
    try:
        check_call(cmd, timeout=10)  # noqa: S603
    except (FileNotFoundError, CalledProcessError, TimeoutExpired):
        logger.warning('Could not generate CITATION.html file:\n%s', ' '.join(cmd))

    # Generate LaTex file resolving citations
    cmd = [
        'pandoc',
        '-s',
        '--bibliography',
        str(boilerplate_bib),
        '--natbib',
        str(log_dir / 'CITATION.md'),
        '-o',
        str(log_dir / 'CITATION.tex'),
    ]
    try:
        check_call(cmd, timeout=10)  # noqa: S603
    except (FileNotFoundError, CalledProcessError, TimeoutExpired):
        logger.warning('Could not generate CITATION.tex file:\n%s', ' '.join(cmd))
    else:
        copyfile(str(boilerplate_bib), str(log_dir / 'CITATION.bib'))
    return retval


def _pprint_subses(subses: list):
    """
    Pretty print a list of subjects and sessions.

    Example
    -------
    >>> _pprint_subses([('01', 'A'), ('02', ['A', 'B']), ('03', None), ('04', ['A'])])
    'sub-01 ses-A, sub-02 (2 sessions), sub-03, sub-04 ses-A'
    """
    output = []
    for subject, session in subses:
        if isinstance(session, list):
            if len(session) > 1:
                output.append(f'sub-{subject} ({len(session)} sessions)')
                continue
            session = session[0]
        if session is None:
            output.append(f'sub-{subject}')
        else:
            output.append(f'sub-{subject} ses-{session}')

    return ', '.join(output)


if __name__ == '__main__':
    raise RuntimeError(
        'smriprep/cli/run.py should not be run directly;\n'
        'Please `pip install` smriprep and use the `smriprep` command'
    )

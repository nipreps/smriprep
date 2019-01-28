#!/usr/bin/env python
# -*- coding: utf-8 -*-
# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
"""
sMRIPrep: Structural MRI PREProcessing workflow
===============================================
"""


def main():
    """Entrypoint"""
    opts = get_parser().parse_args()
    return build_opts(opts)


def check_deps(workflow):
    from nipype.utils.filemanip import which
    return sorted(
        (node.interface.__class__.__name__, node.interface._cmd)
        for node in workflow._get_all_nodes()
        if (hasattr(node.interface, '_cmd') and
            which(node.interface._cmd.split()[0]) is None))


def get_parser():
    """Build parser object"""
    from os.path import abspath
    from argparse import ArgumentParser
    from argparse import RawTextHelpFormatter
    from ..__about__ import __version__

    parser = ArgumentParser(description='sMRIPrep: Structural MRI PREProcessing workflows',
                            formatter_class=RawTextHelpFormatter)

    # Arguments as specified by BIDS-Apps
    # required, positional arguments
    # IMPORTANT: they must go directly with the parser object
    parser.add_argument('bids_dir', action='store',
                        help='the root folder of a BIDS valid dataset (sub-XXXXX folders should '
                             'be found at the top level in this folder).')
    parser.add_argument('output_dir', action='store',
                        help='the output path for the outcomes of preprocessing and visual '
                             'reports')
    parser.add_argument('analysis_level', choices=['participant'],
                        help='processing stage to be run, only "participant" in the case of '
                             'sMRIPrep (see BIDS-Apps specification).')

    # optional arguments
    parser.add_argument('--version', action='version', version='smriprep v{}'.format(__version__))

    g_bids = parser.add_argument_group('Options for filtering BIDS queries')
    g_bids.add_argument('--skip-bids-validation', '--skip_bids_validation', action='store_true',
                        default=False,
                        help='assume the input dataset is BIDS compliant and skip the validation')
    g_bids.add_argument('--participant-label', '--participant_label', action='store', nargs='+',
                        help='a space delimited list of participant identifiers or a single '
                             'identifier (the sub- prefix can be removed)')

    g_perfm = parser.add_argument_group('Options to handle performance')
    g_perfm.add_argument('--nprocs', '--ncpus', '--nthreads', '--n_cpus', '-n-cpus',
                         action='store', type=int,
                         help='number of CPUs to be used.')
    g_perfm.add_argument('--omp-nthreads', action='store', type=int, default=0,
                         help='maximum number of threads per-process')
    g_perfm.add_argument('--mem-gb', '--mem_gb', action='store', default=0, type=float,
                         help='upper bound memory limit for sMRIPrep processes (in GB).')
    g_perfm.add_argument('--low-mem', action='store_true',
                         help='attempt to reduce memory usage (will increase disk usage '
                              'in working directory)')
    g_perfm.add_argument('--use-plugin', action='store', default=None,
                         help='nipype plugin configuration file')
    g_perfm.add_argument('--boilerplate', action='store_true',
                         help='generate boilerplate only')
    g_perfm.add_argument("-v", "--verbose", dest="verbose_count", action="count", default=0,
                         help="increases log verbosity for each occurence, debug level is -vvv")

    g_conf = parser.add_argument_group('Workflow configuration')
    g_conf.add_argument(
        '--longitudinal', action='store_true',
        help='treat dataset as longitudinal - may increase runtime')
    g_conf.add_argument(
        '--template', '--spatial-normalization-target',
        choices=['MNI152NLin2009cAsym', 'MNI152Lin', 'OASIS30ANTs', 'NKI', 'PNC'],
        required=False, action='store', nargs='+', default='MNI152NLin2009cAsym',
        help='spatial normalization targets (one or more TemplateFlow Identifiers')

    #  ANTs options
    g_ants = parser.add_argument_group('Specific options for ANTs registrations')
    g_ants.add_argument('--skull-strip-template', action='store', default='OASIS30ANTs',
                        choices=['OASIS30ANTs', 'NKI', 'MNI152NLin2009cAsym'],
                        help='select ANTs skull-stripping template (default: OASIS30ANTs))')
    g_ants.add_argument('--skull-strip-fixed-seed', action='store_true',
                        help='do not use a random seed for skull-stripping - will ensure '
                             'run-to-run replicability when used with --omp-nthreads 1')

    # FreeSurfer options
    g_fs = parser.add_argument_group('Specific options for FreeSurfer preprocessing')
    g_fs.add_argument(
        '--fs-license-file', metavar='PATH', type=abspath,
        help='Path to FreeSurfer license key file. Get it (for free) by registering'
             ' at https://surfer.nmr.mgh.harvard.edu/registration.html')

    # Surface generation xor
    g_surfs = parser.add_argument_group('Surface preprocessing options')
    g_surfs.add_argument('--no-submm-recon', action='store_false', dest='hires',
                         help='disable sub-millimeter (hires) reconstruction')
    g_surfs_xor = g_surfs.add_mutually_exclusive_group()

    g_surfs_xor.add_argument(
        '--fs-output-spaces', required=False, action='store',
        choices=['fsnative', 'fsaverage', 'fsaverage6', 'fsaverage5'],
        nargs='+', default=['fsaverage5'],
        help='configure Freesurfer\'s output spaces:\n'
             ' - fsnative: individual subject surface\n'
             ' - fsaverage*: FreeSurfer average meshes\n'
             'this argument can be single value or a space delimited list,\n'
             'for example: --fs-output-spaces fsnative fsaverage fsaverage5'
    )
    g_surfs_xor.add_argument('--fs-no-reconall', '--no-freesurfer',
                             action='store_false', dest='run_reconall',
                             help='disable FreeSurfer surface preprocessing.'
                             ' Note : `--no-freesurfer` is deprecated and will be removed in 1.2.'
                             ' Use `--fs-no-reconall` instead.')

    g_other = parser.add_argument_group('Other options')
    g_other.add_argument('-w', '--work-dir', action='store',
                         help='path where intermediate results should be stored')
    g_other.add_argument(
        '--resource-monitor', action='store_true', default=False,
        help='enable Nipype\'s resource monitoring to keep track of memory and CPU usage')
    g_other.add_argument(
        '--reports-only', action='store_true', default=False,
        help='only generate reports, don\'t run workflows. This will only rerun report '
             'aggregation, not reportlet generation for specific nodes.')
    g_other.add_argument(
        '--run-uuid', action='store', default=None,
        help='Specify UUID of previous run, to include error logs in report. '
             'No effect without --reports-only.')
    g_other.add_argument('--write-graph', action='store_true', default=False,
                         help='Write workflow graph.')
    g_other.add_argument('--stop-on-first-crash', action='store_true', default=False,
                         help='Force stopping on first crash, even if a work directory'
                              ' was specified.')
    g_other.add_argument('--notrack', action='store_true', default=False,
                         help='Opt-out of sending tracking information of this run to '
                              'the sMRIPrep developers. This information helps to '
                              'improve sMRIPrep and provides an indicator of real '
                              'world usage crucial for obtaining funding.')
    g_other.add_argument('--sloppy', action='store_true', default=False,
                         help='Use low-quality tools for speed - TESTING ONLY')

    return parser


def build_opts(opts):
    """Entry point"""
    import os
    from os import cpu_count
    from pathlib import Path
    import logging
    import sys
    import gc
    import re
    import psutil
    import warnings
    from multiprocessing import set_start_method, Process, Manager
    set_start_method('forkserver')

    logging.addLevelName(25, 'IMPORTANT')  # Add a new level between INFO and WARNING
    logging.addLevelName(15, 'VERBOSE')  # Add a new level between INFO and DEBUG
    logger = logging.getLogger('cli')

    def _warn_redirect(message, category, filename, lineno, file=None, line=None):
        logger.warning('Captured warning (%s): %s', category, message)

    warnings.showwarning = _warn_redirect
    exec_env = os.name

    # special variable set in the container
    if os.getenv('IS_DOCKER_8395080871'):
        exec_env = 'singularity'
        if 'docker' in Path('/proc/1/cgroup').read_text():
            exec_env = 'docker'
            if os.getenv('DOCKER_VERSION_8395080871'):
                exec_env = 'smriprep-docker'

    sentry_sdk = None
    if not opts.notrack:
        import sentry_sdk
        from ..__about__ import __version__
        environment = "prod"
        release = __version__
        if not __version__:
            environment = "dev"
            release = "dev"
        elif bool(int(os.getenv('SMRIPREP_DEV', 0))) or ('+' in __version__):
            environment = "dev"

        def before_send(event, hints):
            # Filtering log messages about crashed nodes
            if 'logentry' in event and 'message' in event['logentry']:
                msg = event['logentry']['message']
                if msg.startswith("could not run node:"):
                    return None
                elif msg.startswith("Saving crash info to "):
                    return None
                elif re.match("Node .+ failed to run on host .+", msg):
                    return None

            if 'breadcrumbs' in event and isinstance(event['breadcrumbs'], list):
                fingerprints_to_propagate = ['no-disk-space', 'memory-error', 'permission-denied',
                                             'keyboard-interrupt']
                for bc in event['breadcrumbs']:
                    msg = bc.get('message', 'empty-msg')
                    if msg in fingerprints_to_propagate:
                        event['fingerprint'] = [msg]
                        break

            return event

        sentry_sdk.init("https://d5a16b0c38d84d1584dfc93b9fb1ade6@sentry.io/1137693",
                        release=release,
                        environment=environment,
                        before_send=before_send)
        with sentry_sdk.configure_scope() as scope:
            scope.set_tag('exec_env', exec_env)

            if exec_env == 'smriprep-docker':
                scope.set_tag('docker_version', os.getenv('DOCKER_VERSION_8395080871'))

            free_mem_at_start = round(psutil.virtual_memory().free / 1024**3, 1)
            scope.set_tag('free_mem_at_start', free_mem_at_start)
            scope.set_tag('cpu_count', cpu_count())

            # Memory policy may have a large effect on types of errors experienced
            overcommit_memory = Path('/proc/sys/vm/overcommit_memory')
            if overcommit_memory.exists():
                policy = {'0': 'heuristic',
                          '1': 'always',
                          '2': 'never'}.get(overcommit_memory.read_text().strip(), 'unknown')
                scope.set_tag('overcommit_memory', policy)
                if policy == 'never':
                    overcommit_kbytes = Path('/proc/sys/vm/overcommit_memory')
                    kb = overcommit_kbytes.read_text().strip()
                    if kb != '0':
                        limit = '{}kB'.format(kb)
                    else:
                        overcommit_ratio = Path('/proc/sys/vm/overcommit_ratio')
                        limit = '{}%'.format(overcommit_ratio.read_text().strip())
                    scope.set_tag('overcommit_limit', limit)
                else:
                    scope.set_tag('overcommit_limit', 'n/a')
            else:
                scope.set_tag('overcommit_memory', 'n/a')
                scope.set_tag('overcommit_limit', 'n/a')

            for k, v in vars(opts).items():
                scope.set_tag(k, v)

    # Validate inputs
    if not opts.skip_bids_validation:
        print("Making sure the input data is BIDS compliant (warnings can be ignored in most "
              "cases).")
        validate_input_dir(exec_env, opts.bids_dir, opts.participant_label)

    # FreeSurfer license
    default_license = str(Path(os.getenv('FREESURFER_HOME')) / 'license.txt')
    # Precedence: --fs-license-file, $FS_LICENSE, default_license
    license_file = opts.fs_license_file or os.getenv('FS_LICENSE', default_license)
    if not os.path.exists(license_file):
        raise RuntimeError(
            'ERROR: a valid license file is required for FreeSurfer to run. '
            'sMRIPrep looked for an existing license file at several paths, in this '
            'order: 1) command line argument ``--fs-license-file``; 2) ``$FS_LICENSE`` '
            'environment variable; and 3) the ``$FREESURFER_HOME/license.txt`` path. '
            'Get it (for free) by registering at https://'
            'surfer.nmr.mgh.harvard.edu/registration.html')
    os.environ['FS_LICENSE'] = license_file

    # Retrieve logging level
    log_level = int(max(25 - 5 * opts.verbose_count, logging.DEBUG))
    # Set logging
    logger.setLevel(log_level)

    if True:
        from nipype import logging as nlogging
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
        work_dir = retval['work_dir']
        subject_list = retval['subject_list']
        run_uuid = retval['run_uuid']
        if not opts.notrack:
            with sentry_sdk.configure_scope() as scope:
                scope.set_tag('run_uuid', run_uuid)
                scope.set_tag('npart', len(subject_list))

        retcode = retval['return_code']

    if smriprep_wf is None:
        sys.exit(1)

    if opts.write_graph:
        smriprep_wf.write_graph(graph2use="colored", format='svg', simple_form=True)

    if opts.reports_only:
        sys.exit(int(retcode > 0))

    if opts.boilerplate:
        sys.exit(int(retcode > 0))

    # Sentry tracking
    if not opts.notrack:
        sentry_sdk.add_breadcrumb(message='sMRIPrep started', level='info')
        sentry_sdk.capture_message('sMRIPrep started', level='info')

    # Check workflow for missing commands
    missing = check_deps(smriprep_wf)
    if missing:
        print("Cannot run sMRIPrep. Missing dependencies:")
        for iface, cmd in missing:
            print("\t{} (Interface: {})".format(cmd, iface))
        sys.exit(2)

    # Clean up master process before running workflow, which may create forks
    gc.collect()
    try:
        smriprep_wf.run(**plugin_settings)
    except RuntimeError as e:
        errno = 1
        if "Workflow did not execute cleanly" not in str(e):
            sentry_sdk.capture_exception(e)
            raise
    finally:
        from pkg_resources import resource_filename as pkgrf
        from niworkflows.viz.reports import generate_reports

        from ..utils.bids import write_derivative_description
        # Generate reports phase
        errno += generate_reports(subject_list, output_dir, work_dir, run_uuid,
                                  config=pkgrf('smriprep', 'data/reports/config.json'),
                                  sentry_sdk=sentry_sdk)
        write_derivative_description(bids_dir, str(Path(output_dir) / 'smriprep'))

    if not opts.notrack and errno == 0:
        sentry_sdk.capture_message('sMRIPrep finished without errors', level='info')
    sys.exit(int(errno > 0))


def validate_input_dir(exec_env, bids_dir, participant_label):
    import os
    import json
    import tempfile
    import subprocess
    import logging
    from glob import glob

    logger = logging.getLogger('cli')

    # Ignore issues and warnings that should not influence sMRIPrep
    validator_config_dict = {
        "ignore": [
            "EVENTS_COLUMN_ONSET",
            "EVENTS_COLUMN_DURATION",
            "TSV_EQUAL_ROWS",
            "TSV_EMPTY_CELL",
            "TSV_IMPROPER_NA",
            "VOLUME_COUNT_MISMATCH",
            "BVAL_MULTIPLE_ROWS",
            "BVEC_NUMBER_ROWS",
            "DWI_MISSING_BVAL",
            "INCONSISTENT_SUBJECTS",
            "INCONSISTENT_PARAMETERS",
            "BVEC_ROW_LENGTH",
            "B_FILE",
            "PARTICIPANT_ID_COLUMN",
            "PARTICIPANT_ID_MISMATCH",
            "TASK_NAME_MUST_DEFINE",
            "PHENOTYPE_SUBJECTS_MISSING",
            "STIMULUS_FILE_MISSING",
            "DWI_MISSING_BVEC",
            "EVENTS_TSV_MISSING",
            "TSV_IMPROPER_NA",
            "ACQTIME_FMT",
            "Participants age 89 or higher",
            "DATASET_DESCRIPTION_JSON_MISSING",
            "FILENAME_COLUMN",
            "WRONG_NEW_LINE",
            "MISSING_TSV_COLUMN_CHANNELS",
            "MISSING_TSV_COLUMN_IEEG_CHANNELS",
            "MISSING_TSV_COLUMN_IEEG_ELECTRODES",
            "UNUSED_STIMULUS",
            "CHANNELS_COLUMN_SFREQ",
            "CHANNELS_COLUMN_LOWCUT",
            "CHANNELS_COLUMN_HIGHCUT",
            "CHANNELS_COLUMN_NOTCH",
            "CUSTOM_COLUMN_WITHOUT_DESCRIPTION",
            "ACQTIME_FMT",
            "SUSPICIOUSLY_LONG_EVENT_DESIGN",
            "SUSPICIOUSLY_SHORT_EVENT_DESIGN",
            "MALFORMED_BVEC",
            "MALFORMED_BVAL",
            "MISSING_TSV_COLUMN_EEG_ELECTRODES",
            "MISSING_SESSION"
        ],
        "error": ["NO_T1W"],
        "ignoredFiles": ['/dataset_description.json', '/participants.tsv']
    }
    # Limit validation only to data from requested participants
    if participant_label:
        all_subs = set([os.path.basename(i)[4:] for i in glob(os.path.join(bids_dir,
                                                                           "sub-*"))])
        selected_subs = []
        for selected_sub in participant_label:
            if selected_sub.startswith("sub-"):
                selected_subs.append(selected_sub[4:])
            else:
                selected_subs.append(selected_sub)
        selected_subs = set(selected_subs)
        bad_labels = selected_subs.difference(all_subs)
        if bad_labels:
            error_msg = 'Data for requested participant(s) label(s) not found. Could ' \
                        'not find data for participant(s): %s. Please verify the requested ' \
                        'participant labels.'
            if exec_env == 'docker':
                error_msg += ' This error can be caused by the input data not being ' \
                             'accessible inside the docker container. Please make sure all ' \
                             'volumes are mounted properly (see https://docs.docker.com/' \
                             'engine/reference/commandline/run/#mount-volume--v---read-only)'
            if exec_env == 'singularity':
                error_msg += ' This error can be caused by the input data not being ' \
                             'accessible inside the singularity container. Please make sure ' \
                             'all paths are mapped properly (see https://www.sylabs.io/' \
                             'guides/3.0/user-guide/bind_paths_and_mounts.html)'
            raise RuntimeError(error_msg % ','.join(bad_labels))

        ignored_subs = all_subs.difference(selected_subs)
        if ignored_subs:
            for sub in ignored_subs:
                validator_config_dict["ignoredFiles"].append("/sub-%s/**" % sub)
    with tempfile.NamedTemporaryFile('w+') as temp:
        temp.write(json.dumps(validator_config_dict))
        temp.flush()
        try:
            subprocess.check_call(['bids-validator', bids_dir, '-c', temp.name])
        except FileNotFoundError:
            logger.error("bids-validator does not appear to be installed")


def build_workflow(opts, retval):
    """
    Create the Nipype Workflow that supports the whole execution
    graph, given the inputs.
    All the checks and the construction of the workflow are done
    inside this function that has pickleable inputs and output
    dictionary (``retval``) to allow isolation using a
    ``multiprocessing.Process`` that allows smriprep to enforce
    a hard-limited memory-scope.
    """
    import os
    import os.path as op
    from pathlib import Path
    from shutil import copyfile
    from os import cpu_count
    import uuid
    from time import strftime
    from subprocess import check_call, CalledProcessError, TimeoutExpired
    from pkg_resources import resource_filename as pkgrf

    from nipype import logging, config as ncfg
    from ..__about__ import __version__
    from ..workflows.base import init_smriprep_wf
    from niworkflows.utils.bids import collect_participants

    logger = logging.getLogger('nipype.workflow')

    INIT_MSG = """
    Running sMRIPrep version {version}:
      * BIDS dataset path: {bids_dir}.
      * Participant list: {subject_list}.
      * Run identifier: {uuid}.
    """.format

    # Set up some instrumental utilities
    run_uuid = '%s_%s' % (strftime('%Y%m%d-%H%M%S'), uuid.uuid4())

    # First check that bids_dir looks like a BIDS folder
    bids_dir = os.path.abspath(opts.bids_dir)
    subject_list = collect_participants(
        bids_dir, participant_label=opts.participant_label)

    # Load base plugin_settings from file if --use-plugin
    if opts.use_plugin is not None:
        from yaml import load as loadyml
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
            }
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
            'available CPUs (--nprocs/--ncpus=%d)', omp_nthreads, nprocs)

    # Set up directories
    output_dir = op.abspath(opts.output_dir)
    log_dir = op.join(output_dir, 'smriprep', 'logs')
    work_dir = op.abspath(opts.work_dir or 'work')  # Set work/ as default

    # Check and create output and working directories
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(log_dir, exist_ok=True)
    os.makedirs(work_dir, exist_ok=True)

    # Nipype config (logs and execution)
    ncfg.update_config({
        'logging': {
            'log_directory': log_dir,
            'log_to_file': True
        },
        'execution': {
            'crashdump_dir': log_dir,
            'crashfile_format': 'txt',
            'get_linked_libs': False,
            'stop_on_first_crash': opts.stop_on_first_crash or opts.work_dir is None,
        },
        'monitoring': {
            'enabled': opts.resource_monitor,
            'sample_frequency': '0.5',
            'summary_append': True,
        }
    })

    if opts.resource_monitor:
        ncfg.enable_resource_monitor()

    retval['return_code'] = 0
    retval['plugin_settings'] = plugin_settings
    retval['bids_dir'] = bids_dir
    retval['output_dir'] = output_dir
    retval['work_dir'] = work_dir
    retval['subject_list'] = subject_list
    retval['run_uuid'] = run_uuid
    retval['workflow'] = None

    # Called with reports only
    if opts.reports_only:
        from niworkflows.viz.reports import generate_reports

        logger.log(25, 'Running --reports-only on participants %s', ', '.join(subject_list))
        if opts.run_uuid is not None:
            run_uuid = opts.run_uuid
        retval['return_code'] = generate_reports(
            subject_list, output_dir, work_dir, run_uuid,
            config=pkgrf('smriprep', 'data/reports/config.json'))
        return retval

    # Build main workflow
    logger.log(25, INIT_MSG(
        version=__version__,
        bids_dir=bids_dir,
        subject_list=subject_list,
        uuid=run_uuid)
    )

    retval['workflow'] = init_smriprep_wf(
        subject_list=subject_list,
        run_uuid=run_uuid,
        debug=opts.sloppy,
        low_mem=opts.low_mem,
        longitudinal=opts.longitudinal,
        omp_nthreads=omp_nthreads,
        skull_strip_template=opts.skull_strip_template,
        skull_strip_fixed_seed=opts.skull_strip_fixed_seed,
        work_dir=work_dir,
        output_dir=output_dir,
        bids_dir=bids_dir,
        freesurfer=opts.run_reconall,
        fs_spaces=opts.fs_output_spaces,
        template=opts.template,
        hires=opts.hires,
    )
    retval['return_code'] = 0

    logs_path = Path(output_dir) / 'smriprep' / 'logs'
    boilerplate = retval['workflow'].visit_desc()
    (logs_path / 'CITATION.md').write_text(boilerplate)
    logger.log(25, 'Works derived from this sMRIPrep execution should '
               'include the following boilerplate:\n\n%s', boilerplate)

    # Generate HTML file resolving citations
    cmd = ['pandoc', '-s', '--bibliography',
           pkgrf('smriprep', 'data/boilerplate.bib'),
           '--filter', 'pandoc-citeproc',
           '--metadata',  'title="sMRIPrep citation boilerplate"',
           str(logs_path / 'CITATION.md'),
           '-o', str(logs_path / 'CITATION.html')]
    try:
        check_call(cmd, timeout=10)
    except (FileNotFoundError, CalledProcessError, TimeoutExpired):
        logger.warning('Could not generate CITATION.html file:\n%s',
                       ' '.join(cmd))

    # Generate LaTex file resolving citations
    cmd = ['pandoc', '-s', '--bibliography',
           pkgrf('smriprep', 'data/boilerplate.bib'),
           '--natbib', str(logs_path / 'CITATION.md'),
           '-o', str(logs_path / 'CITATION.tex')]
    try:
        check_call(cmd, timeout=10)
    except (FileNotFoundError, CalledProcessError, TimeoutExpired):
        logger.warning('Could not generate CITATION.tex file:\n%s',
                       ' '.join(cmd))
    else:
        copyfile(pkgrf('smriprep', 'data/boilerplate.bib'), str(logs_path / 'CITATION.bib'))
    return retval


if __name__ == '__main__':
    raise RuntimeError("smriprep/cli/run.py should not be run directly;\n"
                       "Please `pip install` smriprep and use the `smriprep` command")

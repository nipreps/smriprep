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
    from pathlib import Path
    from collections import OrderedDict
    from argparse import ArgumentParser
    from argparse import RawTextHelpFormatter
    from templateflow.api import templates
    from .utils import ParseTemplates
    from ..__about__ import __version__

    parser = ArgumentParser(description='sMRIPrep: Structural MRI PREProcessing workflows',
                            formatter_class=RawTextHelpFormatter)

    # Arguments as specified by BIDS-Apps
    # required, positional arguments
    # IMPORTANT: they must go directly with the parser object
    parser.add_argument('bids_dir', action='store', type=Path,
                        help='the root folder of a BIDS valid dataset (sub-XXXXX folders should '
                             'be found at the top level in this folder).')
    parser.add_argument('output_dir', action='store', type=Path,
                        help='the output path for the outcomes of preprocessing and visual '
                             'reports')
    parser.add_argument('analysis_level', choices=['participant'],
                        help='processing stage to be run, only "participant" in the case of '
                             'sMRIPrep (see BIDS-Apps specification).')

    # optional arguments
    parser.add_argument('--version', action='version', version='smriprep v{}'.format(__version__))

    g_bids = parser.add_argument_group('Options for filtering BIDS queries')
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
        '--output-spaces', nargs='+', default=OrderedDict([('MNI152NLin2009cAsym', {})]),
        action=ParseTemplates,
        help='paths or keywords prescribing standard spaces to which normalize the input T1w image'
             ' (valid keywords are: %s).' % ', '.join('"%s"' % s for s in templates()))
    g_conf.add_argument(
        '--longitudinal', action='store_true',
        help='treat dataset as longitudinal - may increase runtime')
    g_conf.add_argument(
        '--template', '--spatial-normalization-target', action='store', type=str,
        choices=[tpl for tpl in templates() if not tpl.startswith('fs')],
        help='DEPRECATED: spatial normalization target (one TemplateFlow Identifier)')

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
        '--fs-license-file', metavar='PATH', type=Path,
        help='Path to FreeSurfer license key file. Get it (for free) by registering'
             ' at https://surfer.nmr.mgh.harvard.edu/registration.html')

    # Surface generation xor
    g_surfs = parser.add_argument_group('Surface preprocessing options')
    g_surfs.add_argument('--no-submm-recon', action='store_false', dest='hires',
                         help='disable sub-millimeter (hires) reconstruction')
    g_surfs_xor = g_surfs.add_mutually_exclusive_group()

    g_surfs_xor.add_argument(
        '--fs-output-spaces', required=False, action='store', nargs='+',
        choices=['fsnative', 'fsaverage', 'fsaverage6', 'fsaverage5'],
        help="""DEPRECATED - configure Freesurfer's output spaces:
  - fsnative: individual subject surface
  - fsaverage*: FreeSurfer average meshes
this argument can be single value or a space delimited list,
for example: --fs-output-spaces fsnative fsaverage fsaverage5."""
    )
    g_surfs_xor.add_argument('--fs-no-reconall', '--no-freesurfer',
                             action='store_false', dest='run_reconall',
                             help='disable FreeSurfer surface preprocessing.'
                             ' Note : `--no-freesurfer` is deprecated and will be removed in 1.2.'
                             ' Use `--fs-no-reconall` instead.')

    g_other = parser.add_argument_group('Other options')
    g_other.add_argument('-w', '--work-dir', action='store', type=Path, default=Path('work'),
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
    from pathlib import Path
    import logging
    import sys
    import gc
    import warnings
    from multiprocessing import set_start_method, Process, Manager
    from nipype import logging as nlogging

    set_start_method('forkserver')

    logging.addLevelName(25, 'IMPORTANT')  # Add a new level between INFO and WARNING
    logging.addLevelName(15, 'VERBOSE')  # Add a new level between INFO and DEBUG
    logger = logging.getLogger('cli')

    def _warn_redirect(message, category, filename, lineno, file=None, line=None):
        logger.warning('Captured warning (%s): %s', category, message)

    warnings.showwarning = _warn_redirect

    # FreeSurfer license
    default_license = str(Path(os.getenv('FREESURFER_HOME')) / 'license.txt')
    # Precedence: --fs-license-file, $FS_LICENSE, default_license
    license_file = Path(opts.fs_license_file or os.getenv('FS_LICENSE', default_license))
    if not license_file.exists():
        raise RuntimeError(
            'ERROR: a valid license file is required for FreeSurfer to run. '
            'sMRIPrep looked for an existing license file at several paths, in this '
            'order: 1) command line argument ``--fs-license-file``; 2) ``$FS_LICENSE`` '
            'environment variable; and 3) the ``$FREESURFER_HOME/license.txt`` path. '
            'Get it (for free) by registering at https://'
            'surfer.nmr.mgh.harvard.edu/registration.html')
    os.environ['FS_LICENSE'] = str(license_file)

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
        work_dir = retval['work_dir']
        subject_list = retval['subject_list']
        run_uuid = retval['run_uuid']
        retcode = retval['return_code']

    if smriprep_wf is None:
        sys.exit(1)

    if opts.write_graph:
        smriprep_wf.write_graph(graph2use="colored", format='svg', simple_form=True)

    if opts.reports_only:
        sys.exit(int(retcode > 0))

    if opts.boilerplate:
        sys.exit(int(retcode > 0))

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
    except RuntimeError:
        errno = 1
    else:
        if opts.run_reconall:
            from templateflow import api
            from niworkflows.utils.misc import _copy_any
            dseg_tsv = str(api.get('fsaverage', suffix='dseg', extensions=['.tsv']))
            _copy_any(dseg_tsv,
                      str(Path(output_dir) / 'smriprep' / 'desc-aseg_dseg.tsv'))
            _copy_any(dseg_tsv,
                      str(Path(output_dir) / 'smriprep' / 'desc-aparcaseg_dseg.tsv'))
        logger.log(25, 'sMRIPrep finished without errors')
    finally:
        from niworkflows.reports import generate_reports
        from ..utils.bids import write_derivative_description

        logger.log(25, 'Writing reports for participants: %s', ', '.join(subject_list))
        # Generate reports phase
        errno += generate_reports(subject_list, output_dir, work_dir, run_uuid,
                                  packagename='smriprep')
        write_derivative_description(bids_dir, str(Path(output_dir) / 'smriprep'))
    sys.exit(int(errno > 0))


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
    from shutil import copyfile
    from os import cpu_count
    from collections import OrderedDict
    import uuid
    from time import strftime
    from subprocess import check_call, CalledProcessError, TimeoutExpired
    from pkg_resources import resource_filename as pkgrf

    from bids import BIDSLayout
    from nipype import logging, config as ncfg
    from ..__about__ import __version__
    from ..workflows.base import init_smriprep_wf
    from niworkflows.utils.bids import collect_participants

    output_spaces = opts.output_spaces

    if opts.template:
        print("""\
The ``--template`` option has been deprecated in version 1.1.2. Your selected template \
"%s" will be inserted at the front of the ``--output-spaces`` argument list. Please update \
your scripts to use ``--output-spaces``.""" % opts.template)
        output_spaces = OrderedDict([(opts.template, {})] + list(output_spaces.items()))

    if opts.fs_output_spaces:
        print("""\
The ``--fs-output-spaces`` option has been deprecated in version 1.1.2. Your selected output \
surfaces "%s" will be appended to the ``--output-spaces`` argument list. Please update \
your scripts to use ``--output-spaces``.""" % ', '.join(opts.fs_output_spaces))
        for fs_space in opts.fs_output_spaces:
            if fs_space not in output_spaces:
                output_spaces[fs_space] = {}

    FS_SPACES = set(['fsnative', 'fsaverage', 'fsaverage6', 'fsaverage5'])
    if opts.run_reconall and not list(FS_SPACES.intersection(output_spaces.keys())):
        print("""\
Although ``--fs-no-reconall`` was not set, no FreeSurfer output space (valid values are: \
%s) was selected. Adding default "fsaverage5" to the \
list of output spaces.""" % ', '.join(FS_SPACES))
        output_spaces['fsaverage5'] = {}

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
    bids_dir = opts.bids_dir.resolve()
    layout = BIDSLayout(str(bids_dir), validate=False)
    subject_list = collect_participants(
        layout, participant_label=opts.participant_label)

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
    output_dir = opts.output_dir.resolve()
    log_dir = output_dir / 'smriprep' / 'logs'
    work_dir = opts.work_dir.resolve()

    # Check and create output and working directories
    log_dir.mkdir(parents=True, exist_ok=True)
    work_dir.mkdir(parents=True, exist_ok=True)

    # Nipype config (logs and execution)
    ncfg.update_config({
        'logging': {
            'log_directory': str(log_dir),
            'log_to_file': True
        },
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
        }
    })

    if opts.resource_monitor:
        ncfg.enable_resource_monitor()

    retval['return_code'] = 0
    retval['plugin_settings'] = plugin_settings
    retval['bids_dir'] = str(bids_dir)
    retval['output_dir'] = str(output_dir)
    retval['work_dir'] = str(work_dir)
    retval['subject_list'] = subject_list
    retval['run_uuid'] = run_uuid
    retval['workflow'] = None

    # Called with reports only
    if opts.reports_only:
        from niworkflows.reports import generate_reports

        logger.log(25, 'Running --reports-only on participants %s', ', '.join(subject_list))
        if opts.run_uuid is not None:
            run_uuid = opts.run_uuid
        retval['return_code'] = generate_reports(
            subject_list, str(output_dir), str(work_dir), run_uuid,
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
        debug=opts.sloppy,
        freesurfer=opts.run_reconall,
        hires=opts.hires,
        layout=layout,
        longitudinal=opts.longitudinal,
        low_mem=opts.low_mem,
        omp_nthreads=omp_nthreads,
        output_dir=str(output_dir),
        output_spaces=output_spaces,
        run_uuid=run_uuid,
        skull_strip_fixed_seed=opts.skull_strip_fixed_seed,
        skull_strip_template=opts.skull_strip_template,
        subject_list=subject_list,
        work_dir=str(work_dir),
    )
    retval['return_code'] = 0

    boilerplate = retval['workflow'].visit_desc()
    (log_dir / 'CITATION.md').write_text(boilerplate)
    logger.log(25, 'Works derived from this sMRIPrep execution should '
               'include the following boilerplate:\n\n%s', boilerplate)

    # Generate HTML file resolving citations
    cmd = ['pandoc', '-s', '--bibliography',
           pkgrf('smriprep', 'data/boilerplate.bib'),
           '--filter', 'pandoc-citeproc',
           '--metadata', 'pagetitle="sMRIPrep citation boilerplate"',
           str(log_dir / 'CITATION.md'),
           '-o', str(log_dir / 'CITATION.html')]
    try:
        check_call(cmd, timeout=10)
    except (FileNotFoundError, CalledProcessError, TimeoutExpired):
        logger.warning('Could not generate CITATION.html file:\n%s',
                       ' '.join(cmd))

    # Generate LaTex file resolving citations
    cmd = ['pandoc', '-s', '--bibliography',
           pkgrf('smriprep', 'data/boilerplate.bib'),
           '--natbib', str(log_dir / 'CITATION.md'),
           '-o', str(log_dir / 'CITATION.tex')]
    try:
        check_call(cmd, timeout=10)
    except (FileNotFoundError, CalledProcessError, TimeoutExpired):
        logger.warning('Could not generate CITATION.tex file:\n%s',
                       ' '.join(cmd))
    else:
        copyfile(pkgrf('smriprep', 'data/boilerplate.bib'), str(log_dir / 'CITATION.bib'))
    return retval


if __name__ == '__main__':
    raise RuntimeError("smriprep/cli/run.py should not be run directly;\n"
                       "Please `pip install` smriprep and use the `smriprep` command")

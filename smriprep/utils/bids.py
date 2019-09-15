# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
"""Utilities to handle BIDS inputs."""
from collections import defaultdict


def collect_derivatives(layout, subject_id, output_spaces, freesurfer):
    """Gather existing derivatives and compose a cache."""
    if not layout.get(scope='derivatives'):
        raise ValueError('Derivatives folder seems empty.')

    common_entities = {
        'subject': subject_id,
        'datatype': 'anat',
        'extension': ['.nii', '.nii.gz'],
        'return_type': 'file',
    }
    spaces = layout.get_spaces(datatype='anat')
    derivs_cache = {
        'template': [s for s in output_spaces if s in spaces],
        't1w_preproc': layout.get(
            desc='preproc', suffix='T1w', space=None, **common_entities)[0],
        't1w_mask': layout.get(
            desc='brain', suffix='mask', space=None, **common_entities)[0],
        't1w_dseg': layout.get(
            desc=None, suffix='dseg', space=None, **common_entities)[0],
        't1w_tpms': layout.get(
            desc=None, label=['CSF', 'WM', 'GM'], suffix='probseg', space=None,
            **common_entities),
    }

    if derivs_cache['template']:
        derivs_cache = defaultdict(list, derivs_cache)

    for space in derivs_cache['template']:
        derivs_cache['std_t1w'] += layout.get(
            desc='preproc', space=space, suffix='T1w', **common_entities)
        derivs_cache['std_mask'] += layout.get(
            desc='brain', suffix='mask', space=space, **common_entities)
        derivs_cache['std_dseg'] += layout.get(
            desc=None, suffix='dseg', space=space, **common_entities)
        derivs_cache['std_tpms'] += layout.get(
            desc=None, label=['CSF', 'WM', 'GM'], suffix='probseg', space=space,
            **common_entities)

        # Retrieve spatial transforms
        xfm_query = common_entities.copy()
        xfm_query.update({'from': 'T1w', 'to': space, 'extension': '.h5',
                          'suffix': 'xfm', 'mode': 'image'})
        derivs_cache['anat2std_xfm'] += layout.get(**xfm_query)

        xfm_query.update({'to': 'T1w', 'from': space})
        derivs_cache['std2anat_xfm'] += layout.get(**xfm_query)

    derivs_cache = dict(derivs_cache)  # Back to a standard dictionary

    if freesurfer:
        derivs_cache['t1w_aseg'] = layout.get(
            desc='aseg', suffix='dseg', space=None, **common_entities)[0]
        derivs_cache['t1w_aparc'] = layout.get(
            desc='aparcaseg', suffix='dseg', space=None, **common_entities)[0]

        fs_query = common_entities.copy()
        fs_query.update({'from': 'T1w', 'to': 'fsnative', 'extension': '.txt',
                         'suffix': 'xfm', 'mode': 'image'})
        derivs_cache['t1w2fsnative_xfm'] = layout.get(**fs_query)[0]
        fs_query.update({'from': 'fsnative', 'to': 'T1w'})
        derivs_cache['fsnative2t1w_xfm'] = layout.get(**fs_query)[0]

        common_entities['extension'] = '.surf.gii'
        derivs_cache['surfaces'] = layout.get(**common_entities)

    for k, v in derivs_cache.items():
        if not v:
            raise ValueError('Empty entry "%s" found in the collected derivatives.' % k)

    return derivs_cache


def write_derivative_description(bids_dir, deriv_dir):
    """
    Write a ``dataset_description.json`` for the derivatives folder.

    .. testsetup::

    >>> from pkg_resources import resource_filename
    >>> from pathlib import Path
    >>> from tempfile import TemporaryDirectory
    >>> tmpdir = TemporaryDirectory()
    >>> bids_dir = resource_filename('smriprep', 'data/tests')
    >>> deriv_desc = Path(tmpdir.name) / 'dataset_description.json'

    .. doctest::

    >>> write_derivative_description(bids_dir, deriv_desc.parent)
    >>> deriv_desc.is_file()
    True

    .. testcleanup::

    >>> tmpdir.cleanup()


    """
    import os
    from pathlib import Path
    import json
    from ..__about__ import __version__, __url__, DOWNLOAD_URL

    bids_dir = Path(bids_dir)
    deriv_dir = Path(deriv_dir)
    desc = {
        'Name': 'sMRIPrep - Structural MRI PREProcessing workflow',
        'BIDSVersion': '1.1.1',
        'PipelineDescription': {
            'Name': 'sMRIPrep',
            'Version': __version__,
            'CodeURL': DOWNLOAD_URL,
        },
        'CodeURL': __url__,
        'HowToAcknowledge':
            'Please cite our paper (https://doi.org/10.1101/306951), and '
            'include the generated citation boilerplate within the Methods '
            'section of the text.',
    }

    # Keys that can only be set by environment
    if 'SMRIPREP_DOCKER_TAG' in os.environ:
        desc['DockerHubContainerTag'] = os.environ['SMRIPREP_DOCKER_TAG']
    if 'SMRIPREP_SINGULARITY_URL' in os.environ:
        singularity_url = os.environ['SMRIPREP_SINGULARITY_URL']
        desc['SingularityContainerURL'] = singularity_url

        singularity_md5 = _get_shub_version(singularity_url)
        if singularity_md5 is not None and singularity_md5 is not NotImplemented:
            desc['SingularityContainerMD5'] = _get_shub_version(singularity_url)

    # Keys deriving from source dataset
    orig_desc = {}
    fname = bids_dir / 'dataset_description.json'
    if fname.exists():
        with fname.open() as fobj:
            orig_desc = json.load(fobj)

    if 'DatasetDOI' in orig_desc:
        desc['SourceDatasetsURLs'] = ['https://doi.org/{}'.format(
            orig_desc['DatasetDOI'])]
    if 'License' in orig_desc:
        desc['License'] = orig_desc['License']

    with (deriv_dir / 'dataset_description.json').open('w') as fobj:
        json.dump(desc, fobj, indent=4)


def _get_shub_version(singularity_url):
    return NotImplemented

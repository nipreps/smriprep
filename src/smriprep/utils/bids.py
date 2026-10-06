# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
#
# Copyright The NiPreps Developers <nipreps@gmail.com>
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
"""Utilities to handle BIDS inputs."""

import logging
from pathlib import Path

from nipost.bids import collect_derivatives, load_spec, sanitize_space

from .. import data

LOGGER = logging.getLogger('nipype.workflow')


def _merge(merged, found, kind, deriv_dir):
    """Update ``merged`` with ``found``, logging any derivative that is replaced."""
    for name, value in found.items():
        if name in merged:
            LOGGER.debug(
                f'Precomputed {kind} {name} found in {deriv_dir}, replacing {merged[name]}'
            )
        merged[name] = value


def collect_anat_derivatives(derivatives, subject_id, std_spaces, session_id=None):
    """Gather precomputed anatomical derivatives from one or more datasets.

    Parameters
    ----------
    derivatives : :obj:`list` of :obj:`os.PathLike`
        Derivatives datasets to search. Later datasets take precedence for each
        image and surface they provide, and for each space they have transforms for.
        Forward and reverse transforms for a space are never combined across datasets.
        Each derivative a later dataset replaces is logged at DEBUG level.
    subject_id : :obj:`str`
        Subject label, without ``sub-``.
    std_spaces : :obj:`list` of :obj:`str`
        Standard spaces to look for transforms to and from.
        Transforms to ``fsnative`` are always searched for.
    session_id : :obj:`str` or :obj:`None`
        Session label, without ``ses-``.

    Returns
    -------
    :obj:`dict`
        ``images`` and ``surfaces`` map query names in ``anat_spec.yml`` to paths.
        ``transforms`` maps each space with precomputed transforms to its
        ``forward`` and/or ``reverse`` transform.

    Raises
    ------
    ValueError
        If a query matches more than one file in a dataset, for example derivatives
        from several sessions when ``session_id`` is not given.
    """
    entities = {'subject': subject_id}
    if session_id:
        entities['session'] = session_id
    # Filenames use the BIDS form of cohort spaces; workflows use the TemplateFlow form
    spaces = {sanitize_space(space): space for space in [*std_spaces, 'fsnative']}
    params = {'space': list(spaces)}
    spec = load_spec(data.load('anat_spec.yml'))

    deriv_cache = {'images': {}, 'surfaces': {}, 'transforms': {}}
    for deriv_dir in derivatives:
        collected = collect_derivatives(deriv_dir, spec=spec, entities=entities, params=params)
        _merge(deriv_cache['images'], collected['images'], 'image', deriv_dir)
        _merge(deriv_cache['surfaces'], collected['surfaces'], 'surface', deriv_dir)
        # Replace whole spaces, so a transform pair always comes from one dataset.
        # Spaces this dataset has no transforms for are empty and must not replace others.
        transforms = {
            spaces[space]: xfms for space, xfms in collected['transforms'].items() if xfms
        }
        _merge(deriv_cache['transforms'], transforms, 'transforms for', deriv_dir)

    return deriv_cache


def write_bidsignore(deriv_dir):
    bids_ignore = [
        '*.html',
        'logs/',
        'figures/',  # Reports
        '*_xfm.*',  # Unspecified transform files
        '*.surf.gii',  # Unspecified structural outputs
    ]
    ignore_file = Path(deriv_dir) / '.bidsignore'

    ignore_file.write_text('\n'.join(bids_ignore) + '\n')


def write_derivative_description(bids_dir, deriv_dir):
    """
    Write a ``dataset_description.json`` for the derivatives folder.

    .. testsetup::

    >>> from smriprep.data import load
    >>> from pathlib import Path
    >>> from tempfile import TemporaryDirectory
    >>> tmpdir = TemporaryDirectory()
    >>> bids_dir = load('tests')
    >>> deriv_desc = Path(tmpdir.name) / 'dataset_description.json'

    .. doctest::

    >>> write_derivative_description(bids_dir, deriv_desc.parent)
    >>> deriv_desc.is_file()
    True

    .. testcleanup::

    >>> tmpdir.cleanup()


    """
    import json
    import os
    from pathlib import Path

    from ..__about__ import DOWNLOAD_URL, __version__

    bids_dir = Path(bids_dir)
    deriv_dir = Path(deriv_dir)
    desc = {
        'Name': 'sMRIPrep - Structural MRI PREProcessing workflow',
        'BIDSVersion': '1.4.0',
        'DatasetType': 'derivative',
        'GeneratedBy': [
            {
                'Name': 'sMRIPrep',
                'Version': __version__,
                'CodeURL': DOWNLOAD_URL,
            }
        ],
        'HowToAcknowledge': 'Please cite our paper (https://doi.org/10.1101/306951), and '
        'include the generated citation boilerplate within the Methods '
        'section of the text.',
    }

    # Keys that can only be set by environment
    if 'SMRIPREP_DOCKER_TAG' in os.environ:
        desc['GeneratedBy'][0]['Container'] = {
            'Type': 'docker',
            'Tag': f'poldracklab/smriprep:{os.environ["SMRIPREP_DOCKER_TAG"]}',
        }
    if 'SMRIPREP_SINGULARITY_URL' in os.environ:
        desc['GeneratedBy'][0]['Container'] = {
            'Type': 'singularity',
            'URI': os.environ['SMRIPREP_SINGULARITY_URL'],
        }

    # Keys deriving from source dataset
    orig_desc = {}
    fname = bids_dir / 'dataset_description.json'
    if fname.exists():
        orig_desc = json.loads(fname.read_text())

    if 'DatasetDOI' in orig_desc:
        doi = orig_desc['DatasetDOI']
        desc['SourceDatasets'] = [
            {
                'URL': f'https://doi.org/{doi}',
                'DOI': doi,
            }
        ]
    if 'License' in orig_desc:
        desc['License'] = orig_desc['License']

    Path.write_text(deriv_dir / 'dataset_description.json', json.dumps(desc, indent=4))

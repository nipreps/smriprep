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


def _find_nearest_path(path_dict, input_path):
    """Find the nearest relative path from an input path to a dictionary of paths.

    If ``input_path`` is not relative to any of the paths in ``path_dict``,
    the absolute path string is returned.

    If ``input_path`` is already a BIDS-URI, then it will be returned unmodified.

    Parameters
    ----------
    path_dict : dict of (str, Path)
        A dictionary of paths.
    input_path : Path
        The input path to match.

    Returns
    -------
    matching_path : str
        The nearest relative path from the input path to a path in the dictionary.
        This is either the concatenation of the associated key from ``path_dict``
        and the relative path from the associated value from ``path_dict`` to ``input_path``,
        or the absolute path to ``input_path`` if no matching path is found from ``path_dict``.

    Examples
    --------
    >>> from pathlib import Path
    >>> path_dict = {
    ...     'bids::': Path('/data/derivatives/fmriprep'),
    ...     'bids:raw:': Path('/data'),
    ...     'bids:deriv-0:': Path('/data/derivatives/source-1'),
    ... }
    >>> input_path = Path('/data/derivatives/source-1/sub-01/func/sub-01_task-rest_bold.nii.gz')
    >>> _find_nearest_path(path_dict, input_path)  # match to 'bids:deriv-0:'
    'bids:deriv-0:sub-01/func/sub-01_task-rest_bold.nii.gz'
    >>> input_path = Path('/out/sub-01/func/sub-01_task-rest_bold.nii.gz')
    >>> _find_nearest_path(path_dict, input_path)  # no match- absolute path
    '/out/sub-01/func/sub-01_task-rest_bold.nii.gz'
    >>> input_path = Path('/data/sub-01/func/sub-01_task-rest_bold.nii.gz')
    >>> _find_nearest_path(path_dict, input_path)  # match to 'bids:raw:'
    'bids:raw:sub-01/func/sub-01_task-rest_bold.nii.gz'
    >>> input_path = 'bids::sub-01/func/sub-01_task-rest_bold.nii.gz'
    >>> _find_nearest_path(path_dict, input_path)  # already a BIDS-URI
    'bids::sub-01/func/sub-01_task-rest_bold.nii.gz'
    >>> input_path = 'https://example.com/sub-01/func/sub-01_task-rest_bold.nii.gz'
    >>> _find_nearest_path(path_dict, input_path)  # already a URL
    'https://example.com/sub-01/func/sub-01_task-rest_bold.nii.gz'
    """
    # Don't modify BIDS-URIs
    if isinstance(input_path, str) and input_path.startswith('bids:'):
        return input_path

    # Only modify URLs if there's a URL in the path_dict
    if isinstance(input_path, str) and input_path.startswith('http'):
        remote_found = False
        for path in path_dict.values():
            if path.startswith('http'):
                remote_found = True
                break

        if not remote_found:
            return input_path

    input_path = Path(input_path)
    matching_path = None
    for key, path in path_dict.items():
        if input_path.is_relative_to(path):
            relative_path = input_path.relative_to(path)
            if (matching_path is None) or (len(relative_path.parts) < len(matching_path.parts)):
                matching_key = key
                matching_path = relative_path

    if matching_path is None:
        matching_path = str(input_path.absolute())
    else:
        matching_path = f'{matching_key}{matching_path}'

    return matching_path

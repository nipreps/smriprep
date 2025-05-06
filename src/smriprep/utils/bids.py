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
"""Utilities to handle BIDS inputs."""

from json import loads
from pathlib import Path

from bids.layout import BIDSLayout
from niworkflows.data import load as nwf_load

import smriprep


def collect_derivatives(
    derivatives_dir,
    subject_id,
    std_spaces,
    spec=None,
    patterns=None,
    session_id=None,
):
    """Gather existing derivatives and compose a cache."""
    if spec is None or patterns is None:
        _spec, _patterns = tuple(loads(smriprep.load_data('io_spec.json').read_text()).values())

        if spec is None:
            spec = _spec
        if patterns is None:
            patterns = _patterns

    deriv_config = nwf_load('nipreps.json')
    layout = BIDSLayout(derivatives_dir, config=deriv_config, validate=False)

    derivs_cache = {}
    for key, qry in spec['baseline'].items():
        qry['subject'] = subject_id
        if session_id:
            qry['session'] = session_id

        item = layout.get(return_type='filename', **qry)
        if not item:
            continue

        derivs_cache[f't1w_{key}'] = item[0] if len(item) == 1 else item

    transforms = derivs_cache.setdefault('transforms', {})
    for _space in std_spaces:
        space = _space.replace(':cohort-', '+')
        for key, qry in spec['transforms'].items():
            qry = qry.copy()
            qry['subject'] = subject_id
            if session_id:
                qry['session'] = session_id

            qry['from'] = qry['from'] or space
            qry['to'] = qry['to'] or space
            item = layout.get(return_type='filename', **qry)
            if not item:
                continue
            transforms.setdefault(_space, {})[key] = item[0] if len(item) == 1 else item

    for key, qry in spec['surfaces'].items():
        qry['subject'] = subject_id
        if session_id:
            qry['session'] = session_id

        item = layout.get(return_type='filename', **qry)
        if not item or len(item) != 2:
            continue

        derivs_cache[key] = sorted(item)

    return derivs_cache


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

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
"""Tests for BIDS I/O helpers."""

import json

from smriprep.utils.bids import write_bidsignore, write_derivative_description


def test_write_bidsignore(tmp_path):
    write_bidsignore(tmp_path)
    bidsignore = (tmp_path / '.bidsignore').read_text().splitlines()
    assert bidsignore == ['*.html', 'logs/', 'figures/', '*_xfm.*', '*.surf.gii']


def test_write_derivative_description_minimal(tmp_path):
    bids_dir = tmp_path / 'bids'
    deriv_dir = tmp_path / 'derivatives'
    bids_dir.mkdir()
    deriv_dir.mkdir()

    write_derivative_description(bids_dir, deriv_dir)
    desc = json.loads((deriv_dir / 'dataset_description.json').read_text())

    assert desc['Name'].startswith('sMRIPrep')
    assert desc['DatasetType'] == 'derivative'
    assert desc['GeneratedBy'][0]['Name'] == 'sMRIPrep'
    assert 'Container' not in desc['GeneratedBy'][0]
    assert 'SourceDatasets' not in desc
    assert 'License' not in desc


def test_write_derivative_description_propagates_source_metadata(tmp_path):
    bids_dir = tmp_path / 'bids'
    deriv_dir = tmp_path / 'derivatives'
    bids_dir.mkdir()
    deriv_dir.mkdir()

    src_desc = {
        'DatasetDOI': '10.18112/openneuro.ds000001.v1.0.0',
        'License': 'CC0',
    }
    (bids_dir / 'dataset_description.json').write_text(json.dumps(src_desc))

    write_derivative_description(bids_dir, deriv_dir)
    desc = json.loads((deriv_dir / 'dataset_description.json').read_text())

    assert desc['SourceDatasets'][0]['DOI'] == src_desc['DatasetDOI']
    assert desc['SourceDatasets'][0]['URL'] == f'https://doi.org/{src_desc["DatasetDOI"]}'
    assert desc['License'] == 'CC0'


def test_write_derivative_description_container_precedence(tmp_path, monkeypatch):
    bids_dir = tmp_path / 'bids'
    deriv_dir = tmp_path / 'derivatives'
    bids_dir.mkdir()
    deriv_dir.mkdir()

    monkeypatch.setenv('SMRIPREP_DOCKER_TAG', '24.0.0')
    monkeypatch.setenv('SMRIPREP_SINGULARITY_URL', 'library://smriprep:24.0.0')
    write_derivative_description(bids_dir, deriv_dir)

    desc = json.loads((deriv_dir / 'dataset_description.json').read_text())
    container = desc['GeneratedBy'][0]['Container']
    assert container == {
        'Type': 'singularity',
        'URI': 'library://smriprep:24.0.0',
    }

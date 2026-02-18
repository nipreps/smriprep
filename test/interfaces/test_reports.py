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
"""Tests for report interfaces."""

from pathlib import Path

import pytest

from smriprep.interfaces.reports import AboutSummary, SubjectSummary, SummaryInterface


class _DummySummary(SummaryInterface):
    def _generate_segment(self):
        return '<p>dummy</p>'


def test_summaryinterface_writes_html(tmp_path):
    result = _DummySummary().run(cwd=tmp_path)
    report = Path(result.outputs.out_report)
    assert report.exists()
    assert report.read_text() == '<p>dummy</p>'


def test_subjectsummary_not_run(tmp_path):
    t1w = tmp_path / 'sub-01_T1w.nii.gz'
    t1w.write_text('x')
    result = SubjectSummary(
        t1w=[str(t1w)],
        t2w=[],
        subject_id='sub-01',
    ).run(cwd=tmp_path)
    html = Path(result.outputs.out_report).read_text()
    assert 'Not run' in html
    assert 'sub-01' in html
    assert result.outputs.subject_id == 'sub-01'


@pytest.mark.parametrize(
    ('cmdline', 'status'),
    [
        ('echo recon-all: nothing to do', 'Pre-existing directory'),
        ('recon-all -subjid sub-01', 'Run by sMRIPrep'),
    ],
)
def test_subjectsummary_freesurfer_status(cmdline, status, monkeypatch, tmp_path):
    t1w = tmp_path / 'sub-01_T1w.nii.gz'
    t1w.write_text('x')
    subjects_dir = tmp_path / 'freesurfer'
    subjects_dir.mkdir()

    class _FakeRecon:
        def __init__(self, **_kwargs):
            self.cmdline = cmdline

    monkeypatch.setattr('smriprep.interfaces.reports.fs.ReconAll', _FakeRecon)
    result = SubjectSummary(
        t1w=[str(t1w)],
        t2w=[str(t1w)],
        subjects_dir=str(subjects_dir),
        subject_id='sub-01',
        output_spaces=['MNI152NLin2009cAsym', 'fsaverage5'],
    ).run(cwd=tmp_path)

    html = Path(result.outputs.out_report).read_text()
    assert status in html
    assert 'MNI152NLin2009cAsym, fsaverage5' in html
    assert '(+ 1 T2-weighted)' in html


def test_aboutsummary_uses_timestamp(monkeypatch, tmp_path):
    monkeypatch.setattr('smriprep.interfaces.reports.time.strftime', lambda *_a, **_k: '2024-01-01')
    result = AboutSummary(version='1.0.0', command='smriprep ...').run(cwd=tmp_path)
    html = Path(result.outputs.out_report).read_text()
    assert '1.0.0' in html
    assert 'smriprep ...' in html
    assert '2024-01-01' in html

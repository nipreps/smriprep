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
"""Tests for TemplateFlow interfaces and helpers."""

from pathlib import Path

from nipype.interfaces.base import Undefined

from smriprep.interfaces.templateflow import TemplateDesc, TemplateFlowSelect, fetch_template_files


def test_templatedesc():
    result = TemplateDesc(template='MNIPediatricAsym:cohort-2').run()
    assert result.outputs.name == 'MNIPediatricAsym'
    assert result.outputs.spec == {'cohort': '2'}


def test_fetch_template_files_defaults_and_fallback(monkeypatch):
    calls = []
    monkeypatch.setattr(
        'smriprep.interfaces.templateflow.tf.TF_LAYOUT.get_resolutions',
        lambda template: [1, 2],
    )

    def _fake_get(template, **spec):
        calls.append((template, spec.copy()))
        if spec.get('suffix') == 'T1w':
            return '/tpl-T1w.nii.gz'
        if spec.get('suffix') == 'mask' and spec.get('desc') == 'brain':
            return None
        if spec.get('suffix') == 'mask' and spec.get('label') == 'brain':
            return '/tpl-mask.nii.gz'
        if spec.get('suffix') == 'T2w':
            return None
        return '/unused'

    monkeypatch.setattr('smriprep.interfaces.templateflow.tf.get', _fake_get)
    files = fetch_template_files('MNI152NLin2009cAsym', specs={})

    assert files['t1w'] == '/tpl-T1w.nii.gz'
    assert files['mask'] == '/tpl-mask.nii.gz'
    assert files['t2w'] is Undefined
    assert any(call[1].get('resolution') == [1] for call in calls)


def test_fetch_template_files_resolution_fallback(monkeypatch):
    monkeypatch.setattr(
        'smriprep.interfaces.templateflow.tf.TF_LAYOUT.get_resolutions',
        lambda template: [2],
    )

    seen = {}

    def _fake_get(template, **spec):
        if spec.get('suffix') == 'T1w':
            seen['t1w_resolution'] = spec.get('resolution')
            return '/tpl-T1w.nii.gz'
        if spec.get('suffix') == 'mask':
            return '/tpl-mask.nii.gz'
        if spec.get('suffix') == 'T2w':
            return '/tpl-T2w.nii.gz'
        return '/unused'

    monkeypatch.setattr('smriprep.interfaces.templateflow.tf.get', _fake_get)
    files = fetch_template_files('MNI152NLin2009cAsym', specs={'resolution': [99]})
    assert files['t2w'] == '/tpl-T2w.nii.gz'
    assert seen['t1w_resolution'] == 2


def test_fetch_template_files_preserves_explicit_specs(monkeypatch):
    monkeypatch.setattr(
        'smriprep.interfaces.templateflow.tf.TF_LAYOUT.get_resolutions',
        lambda template: [1],
    )

    seen = {}

    def _fake_get(template, **spec):
        seen['spec'] = spec
        return '/tpl-file.nii.gz'

    monkeypatch.setattr('smriprep.interfaces.templateflow.tf.get', _fake_get)
    fetch_template_files('MNIPediatricAsym:cohort-5', specs={'cohort': '3'})
    assert seen['spec']['cohort'] == '3'


def test_templateflowselect_runs_with_overrides(monkeypatch, tmp_path):
    t1w = tmp_path / 'tpl-T1w.nii.gz'
    mask = tmp_path / 'tpl-mask.nii.gz'
    t2w = tmp_path / 'tpl-T2w.nii.gz'
    for path in (t1w, mask, t2w):
        path.write_text('x')

    received = {}

    def _fake_fetch(template, specs, sloppy=False):
        received['template'] = template
        received['specs'] = specs.copy()
        return {'t1w': str(t1w), 'mask': str(mask), 't2w': str(t2w)}

    monkeypatch.setattr('smriprep.interfaces.templateflow.fetch_template_files', _fake_fetch)

    interface = TemplateFlowSelect(resolution=[2], cohort=['3'], atlas=['atlasA'])
    interface.inputs.template = 'MNIPediatricAsym:cohort-5'
    interface.inputs.template_spec = {'cohort': '4'}
    result = interface.run(cwd=tmp_path)

    assert received['template'] == 'MNIPediatricAsym:cohort-5'
    assert received['specs']['cohort'] == ['3']
    assert received['specs']['resolution'] == [2]
    assert received['specs']['atlas'] == ['atlasA']
    assert Path(result.outputs.t1w_file) == t1w
    assert Path(result.outputs.brain_mask) == mask

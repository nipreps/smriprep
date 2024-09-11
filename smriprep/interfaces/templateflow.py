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
"""Interfaces to get templates from TemplateFlow."""

import logging

from nipype.interfaces.base import (
    BaseInterfaceInputSpec,
    File,
    InputMultiObject,
    SimpleInterface,
    TraitedSpec,
    isdefined,
    traits,
)
from templateflow import api as tf

LOGGER = logging.getLogger('nipype.interface')


class _TemplateFlowSelectInputSpec(BaseInterfaceInputSpec):
    template = traits.Str(mandatory=True, desc='Template ID')
    atlas = InputMultiObject(traits.Str, desc='Specify an atlas')
    cohort = InputMultiObject(traits.Either(traits.Str, traits.Int), desc='Specify a cohort')
    resolution = InputMultiObject(traits.Int, desc='Specify a template resolution index')
    template_spec = traits.DictStrAny(
        {'atlas': None, 'cohort': None}, usedefault=True, desc='Template specifications'
    )
    get_T2w = traits.Bool(False, usedefault=True, desc='Get the T2w if available')


class _TemplateFlowSelectOutputSpec(TraitedSpec):
    t1w_file = File(exists=True, desc='T1w template')
    t2w_file = File(exists=True, desc='T2w template')
    brain_mask = File(exists=True, desc="Template's brain mask")


class TemplateFlowSelect(SimpleInterface):
    """
    Select TemplateFlow elements.

    >>> select = TemplateFlowSelect(resolution=1, get_T2w=True)
    >>> select.inputs.template = 'MNI152NLin2009cAsym'
    >>> result = select.run()
    >>> result.outputs.t1w_file  # doctest: +ELLIPSIS
    '.../tpl-MNI152NLin2009cAsym_res-01_T1w.nii.gz'

    >>> result.outputs.brain_mask  # doctest: +ELLIPSIS
    '.../tpl-MNI152NLin2009cAsym_res-01_desc-brain_mask.nii.gz'

    >>> result.outputs.t2w_file  # doctest: +ELLIPSIS
    '.../tpl-MNI152NLin2009cAsym_res-01_T2w.nii.gz'

    >>> select = TemplateFlowSelect()
    >>> select.inputs.template = 'MNIPediatricAsym'
    >>> select.inputs.template_spec = {'cohort': 5, 'resolution': 1}
    >>> result = select.run()
    >>> result.outputs.t1w_file  # doctest: +ELLIPSIS
    '.../tpl-MNIPediatricAsym_cohort-5_res-1_T1w.nii.gz'

    >>> select = TemplateFlowSelect(resolution=2)
    >>> select.inputs.template = 'MNIPediatricAsym:cohort-5'
    >>> select.inputs.template_spec = {'resolution': 1}
    >>> result = select.run()
    >>> result.outputs.t1w_file  # doctest: +ELLIPSIS
    '.../tpl-MNIPediatricAsym_cohort-5_res-2_T1w.nii.gz'

    >>> select = TemplateFlowSelect()
    >>> select.inputs.template = 'MNIPediatricAsym:cohort-2'
    >>> select.inputs.template_spec = {'cohort': 5, 'resolution': 1}
    >>> result = select.run()
    >>> result.outputs.t1w_file  # doctest: +ELLIPSIS
    '.../tpl-MNIPediatricAsym_cohort-5_res-1_T1w.nii.gz'

    >>> select = TemplateFlowSelect()
    >>> select.inputs.template = 'MNI305'
    >>> select.inputs.template_spec = {'resolution': 1}
    >>> result = select.run()
    >>> result.outputs.t1w_file  # doctest: +ELLIPSIS
    '.../tpl-MNI305_T1w.nii.gz'

    """

    input_spec = _TemplateFlowSelectInputSpec
    output_spec = _TemplateFlowSelectOutputSpec

    def _run_interface(self, runtime):
        specs = self.inputs.template_spec
        if isdefined(self.inputs.resolution):
            specs['resolution'] = self.inputs.resolution
        if isdefined(self.inputs.atlas):
            specs['atlas'] = self.inputs.atlas
        if isdefined(self.inputs.cohort):
            specs['cohort'] = self.inputs.cohort

        files = fetch_template_files(
            self.inputs.template, specs, self.inputs.get_T2w
        )
        self._results['t1w_file'] = files['t1w']
        if self.inputs.get_T2w and files['t2w'] is not None:
            self._results['t2w_file'] = files['t2w']
        self._results['brain_mask'] = files['mask']
        return runtime


class _TemplateDescInputSpec(BaseInterfaceInputSpec):
    template = traits.Str(mandatory=True, desc='univocal template identifier')


class _TemplateDescOutputSpec(TraitedSpec):
    name = traits.Str(desc='template identifier')
    spec = traits.Dict(desc='template arguments')


class TemplateDesc(SimpleInterface):
    """
    Select template description and name pairs.

    This interface is necessary to ensure the good functioning
    with iterables and JoinNodes.

    >>> select = TemplateDesc(template='MNI152NLin2009cAsym')
    >>> result = select.run()
    >>> result.outputs.name
    'MNI152NLin2009cAsym'

    >>> result.outputs.spec
    {}

    >>> select = TemplateDesc(template='MNIPediatricAsym:cohort-2')
    >>> result = select.run()
    >>> result.outputs.name
    'MNIPediatricAsym'

    >>> result.outputs.spec
    {'cohort': '2'}

    """

    input_spec = _TemplateDescInputSpec
    output_spec = _TemplateDescOutputSpec

    def _run_interface(self, runtime):
        _split = self.inputs.template.split(':')
        self._results['name'] = _split[0]

        self._results['spec'] = {}
        if len(_split) > 1:
            for desc in _split[1:]:
                descsplit = desc.split('-')
                self._results['spec'][descsplit[0]] = descsplit[1]
        return runtime


def fetch_template_files(
    template: str,
    specs: dict | None = None,
    sloppy: bool = False,
    get_T2w: bool = False,
) -> dict:
    if specs is None:
        specs = {}

    name = template.strip(':').split(':', 1)
    if len(name) > 1:
        specs.update(
            {
                k: v
                for modifier in name[1].split(':')
                for k, v in [tuple(modifier.split('-'))]
                if k not in specs
            }
        )

    if res := specs.pop('res', None):
        if res != 'native':
            specs['resolution'] = res

    if not specs.get('resolution'):
        specs['resolution'] = 2 if sloppy else 1

    if specs.get('resolution') and not isinstance(specs['resolution'], list):
        specs['resolution'] = [specs['resolution']]

    available_resolutions = tf.TF_LAYOUT.get_resolutions(template=name[0])
    if specs.get('resolution') and not set(specs['resolution']) & set(available_resolutions):
        fallback_res = available_resolutions[0] if available_resolutions else None
        LOGGER.warning(
            f"Template {name[0]} does not have resolution(s): {specs['resolution']}."
            f"Falling back to resolution: {fallback_res}."
        )
        specs['resolution'] = fallback_res

    files = {}
    files['t1w'] = tf.get(name[0], desc=None, suffix='T1w', **specs)
    if get_T2w:
        files['t2w'] = tf.get(name[0], desc=None, suffix='T2w', **specs)
    files['mask'] = tf.get(name[0], desc='brain', suffix='mask', **specs) or tf.get(
        name[0], label='brain', suffix='mask', **specs
    )
    return files

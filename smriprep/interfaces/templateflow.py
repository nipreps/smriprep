# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
"""Interfaces to get templates from TemplateFlow."""
from templateflow import api as tf
from nipype.interfaces.base import (
    SimpleInterface, BaseInterfaceInputSpec, TraitedSpec,
    isdefined, traits, File, InputMultiObject,
)


class _TemplateFlowSelectInputSpec(BaseInterfaceInputSpec):
    template = traits.Str('MNI152NLin2009cAsym', mandatory=True, desc='Template ID')
    atlas = InputMultiObject(traits.Str, desc='Specify an atlas')
    resolution = InputMultiObject(traits.Int, desc='Specify a template resolution index')
    template_spec = traits.DictStrAny(
        {'atlas': None}, usedefault=True, desc='Template specifications')


class _TemplateFlowSelectOutputSpec(TraitedSpec):
    t1w_file = File(exists=True, desc='T1w template')
    brain_mask = File(exists=True, desc="Template's brain mask")


class TemplateFlowSelect(SimpleInterface):
    """
    Select TemplateFlow elements.

    >>> select = TemplateFlowSelect(resolution=1)
    >>> select.inputs.template = 'MNI152NLin2009cAsym'
    >>> result = select.run()
    >>> result.outputs.t1w_file  # doctest: +ELLIPSIS
    '.../tpl-MNI152NLin2009cAsym_res-01_T1w.nii.gz'

    >>> result.outputs.brain_mask  # doctest: +ELLIPSIS
    '.../tpl-MNI152NLin2009cAsym_res-01_desc-brain_mask.nii.gz'

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

    """

    input_spec = _TemplateFlowSelectInputSpec
    output_spec = _TemplateFlowSelectOutputSpec

    def _run_interface(self, runtime):
        specs = self.inputs.template_spec
        if isdefined(self.inputs.resolution):
            specs['resolution'] = self.inputs.resolution
        if isdefined(self.inputs.atlas):
            specs['atlas'] = self.inputs.atlas

        name = self.inputs.template.strip(":").split(":", 1)
        if len(name) > 1:
            specs.update({
                k: v for modifier in name[1].split(":")
                for k, v in [tuple(modifier.split("-"))]
                if k not in specs
            })

        self._results['t1w_file'] = tf.get(
            name[0], desc=None, suffix='T1w', **specs
        )

        self._results['brain_mask'] = tf.get(
            name[0], desc='brain', suffix='mask', **specs
        )
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

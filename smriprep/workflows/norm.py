# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
"""
Spatial normalization workflows
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. autofunction:: init_anat_norm_wf

"""
from nipype.pipeline import engine as pe
from nipype.interfaces import (
    utility as niu,
    freesurfer as fs,
    fsl,
    image,
)

from nipype.interfaces.ants.base import Info as ANTsInfo

from templateflow.api import get as get_template, get_metadata, templates
from niworkflows.engine.workflows import LiterateWorkflow as Workflow
from niworkflows.interfaces.registration import RobustMNINormalizationRPT
from niworkflows.interfaces.fixes import FixHeaderApplyTransforms as ApplyTransforms
from ..interfaces import DerivativesDataSink


def init_anat_norm_wf(
    debug,
    omp_nthreads,
    reportlets_dir,
    template_spec,
):
    """
    An individual spatial normalization workflow using ``antsRegistration``.

    .. workflow ::
        :graph2use: orig
        :simple_form: yes

        from smriprep.workflows.norm import init_anat_norm_wf
        wf = init_anat_norm_wf(

        )

    """
    template = template_spec.split(':')[0]
    templateflow = template in templates()

    if not templateflow:
        raise NotImplementedError(
            'This is embarrassing - custom templates are not (yet) supported.'
            'Please make sure none of the options already available via TemplateFlow '
            'fit your needs.')

    template_meta = get_metadata(template)
    template_refs = ['@%s' % template.lower()]

    if template_meta.get('RRID', None):
        template_refs += ['RRID:%s' % template_meta['RRID']]

    workflow = Workflow('anat_norm_wf_%s' % template)
    workflow.__desc__ = """\
Spatial normalization to the *{template_name}* [{template_refs};
TemplateFlow ID: {template}] was performed through nonlinear
registration with `antsRegistration` (ANTs {ants_ver}), using
brain-extracted versions of both T1w reference and the T1w template.
""".format(
        ants_ver=ANTsInfo.version() or '<ver>',
        template=template,
        template_name=template_meta['Name'],
        template_refs=', '.join(template_refs),
    )

    inputnode = pe.Node(niu.IdentityInterface(fields=[
        'moving_image', 'moving_mask', 'moving_segmentation', 'moving_tpms',
        'lesion_mask', 'orig_t1w']),
        name='inputnode')
    outputnode = pe.Node(niu.IdentityInterface(
        fields=['warped', 'forward_transform', 'reverse_transform',
                'tpl_mask', 'tpl_seg', 'tpl_tpms', 'template']),
        name='outputnode')
    outputnode.inputs.template = template

    registration = pe.Node(RobustMNINormalizationRPT(
        float=True, generate_report=True,
        flavor=['precise', 'testing'][debug],
    ), name='registration', n_procs=omp_nthreads, mem_gb=2)

    # Resample the brain mask and the tissue probability maps into template space
    tpl_mask = pe.Node(ApplyTransforms(dimension=3, default_value=0, float=True,
                                       interpolation='MultiLabel'), name='tpl_mask')

    tpl_seg = pe.Node(ApplyTransforms(dimension=3, default_value=0, float=True,
                                      interpolation='MultiLabel'), name='tpl_seg')

    tpl_tpms = pe.MapNode(ApplyTransforms(dimension=3, default_value=0, float=True,
                                          interpolation='BSpline'),
                          iterfield=['input_image'], name='tpl_tpms')

    # TODO isolate the spatial normalization workflow #############
    ref_img = str(get_template(template, resolution=1, desc=None, suffix='T1w',
                               extensions=['.nii', '.nii.gz']))

    registration.inputs.template = template
    tpl_mask.inputs.reference_image = ref_img
    tpl_seg.inputs.reference_image = ref_img
    tpl_tpms.inputs.reference_image = ref_img

    workflow.connect([
        (inputnode, registration, [
            ('moving_image', 'moving_image'),
            ('moving_mask', 'moving_mask'),
            ('lesion_mask', 'lesion_mask')]),
        (inputnode, tpl_mask, [('moving_mask', 'input_image')]),
        (registration, tpl_mask, [('composite_transform', 'transforms')]),
        (inputnode, tpl_seg, [('moving_segmentation', 'input_image')]),
        (registration, tpl_seg, [('composite_transform', 'transforms')]),
        (inputnode, tpl_tpms, [('moving_tpms', 'input_image')]),
        (registration, tpl_tpms, [('composite_transform', 'transforms')]),
        (registration, outputnode, [
            ('warped_image', 'warped'),
            ('composite_transform', 'forward_transform'),
            ('inverse_composite_transform', 'reverse_transform')]),
        (tpl_mask, outputnode, [('output_image', 'tpl_mask')]),
        (tpl_seg, outputnode, [('output_image', 'tpl_seg')]),
        (tpl_tpms, outputnode, [('output_image', 'tpl_tpms')]),
    ])

    # Store report
    ds_t1_2_tpl_report = pe.Node(
        DerivativesDataSink(base_directory=reportlets_dir, space=template,
                            suffix='t1w'),
        name='ds_t1_2_tpl_report', run_without_submitting=True)

    workflow.connect([
        (inputnode, ds_t1_2_tpl_report, [('orig_t1w', 'source_file')]),
        (registration, ds_t1_2_tpl_report, [('out_report', 'in_file')]),
    ])

    return workflow, template

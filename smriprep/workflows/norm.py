# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
"""
Spatial normalization workflows
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. autofunction:: init_anat_norm_wf

"""
from collections import defaultdict
from nipype.pipeline import engine as pe
from nipype.interfaces import utility as niu

from nipype.interfaces.ants.base import Info as ANTsInfo

from templateflow.api import get_metadata, templates
from niworkflows.engine.workflows import LiterateWorkflow as Workflow
from niworkflows.interfaces.registration import RobustMNINormalizationRPT
from niworkflows.interfaces.fixes import FixHeaderApplyTransforms as ApplyTransforms
from ..interfaces import DerivativesDataSink


def init_anat_norm_wf(
    debug,
    omp_nthreads,
    reportlets_dir,
    template_list,
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

    templateflow = templates()
    if any(template not in templateflow for template in template_list):
        raise NotImplementedError(
            'This is embarrassing - custom templates are not (yet) supported.'
            'Please make sure none of the options already available via TemplateFlow '
            'fit your needs.')

    workflow = Workflow('anat_norm_wf')

    workflow.__desc__ = """\
Volume-based spatial normalization to {targets} ({targets_id}) was performed through
nonlinear registration with `antsRegistration` (ANTs {ants_ver}),
using brain-extracted versions of both T1w reference and the T1w template.
The following template{tpls} selected for spatial normalization:
""".format(
        ants_ver=ANTsInfo.version() or '(version unknown)',
        targets='%s standard space%s' % (defaultdict(
            'several'.format, {1: 'one', 2: 'two', 3: 'three', 4: 'four'})[len(template_list)],
            's' * (len(template_list) != 1)),
        targets_id=', '.join(template_list),
        tpls=(' was', 's were')[len(template_list) != 1]
    )

    # Append template citations to description
    for template in template_list:
        template_meta = get_metadata(template)
        template_refs = ['@%s' % template.lower()]

        if template_meta.get('RRID', None):
            template_refs += ['RRID:%s' % template_meta['RRID']]

        workflow.__desc__ += """\
*{template_name}* [{template_refs}; TemplateFlow ID: {template}]""".format(
            template=template,
            template_name=template_meta['Name'],
            template_refs=', '.join(template_refs))
        workflow.__desc__ += (', ', '.')[template == template_list[-1]]

    inputnode = pe.Node(niu.IdentityInterface(fields=[
        'moving_image', 'moving_mask', 'moving_segmentation', 'moving_tpms',
        'lesion_mask', 'orig_t1w', 'template']),
        name='inputnode')
    inputnode.iterables = [('template', template_list)]
    outputnode = pe.Node(niu.IdentityInterface(
        fields=['warped', 'forward_transform', 'reverse_transform',
                'tpl_mask', 'tpl_seg', 'tpl_tpms', 'template']),
        name='outputnode')

    fixed_tpl = pe.Node(niu.Function(function=_templateflow_ds),
                        name='fixed_tpl', run_without_submitting=True)

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

    workflow.connect([
        (inputnode, fixed_tpl, [('template', 'template')]),
        (inputnode, registration, [('template', 'template')]),
        (inputnode, registration, [
            ('moving_image', 'moving_image'),
            ('moving_mask', 'moving_mask'),
            ('lesion_mask', 'lesion_mask')]),
        (inputnode, tpl_mask, [('moving_mask', 'input_image')]),
        (fixed_tpl, tpl_mask, [('out', 'reference_image')]),
        (fixed_tpl, tpl_seg, [('out', 'reference_image')]),
        (fixed_tpl, tpl_tpms, [('out', 'reference_image')]),
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
        (inputnode, outputnode, [('template', 'template')]),
    ])

    # Store report
    ds_t1_2_tpl_report = pe.Node(
        DerivativesDataSink(base_directory=reportlets_dir,
                            suffix='t1w'),
        name='ds_t1_2_tpl_report', run_without_submitting=True)

    workflow.connect([
        (inputnode, ds_t1_2_tpl_report, [
            ('template', 'space'),
            ('orig_t1w', 'source_file')]),
        (registration, ds_t1_2_tpl_report, [('out_report', 'in_file')]),
    ])
    return workflow


def _templateflow_ds(template, resolution=1, desc=None, suffix='T1w',
                     extensions=('.nii', '.nii.gz')):
    from templateflow.api import get as get_template
    return str(get_template(template, resolution=resolution, desc=desc,
                            suffix=suffix, extensions=extensions))

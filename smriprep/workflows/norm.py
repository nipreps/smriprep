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
from niworkflows.interfaces.ants import ImageMath
from niworkflows.interfaces.mni import RobustMNINormalization
from niworkflows.interfaces.fixes import FixHeaderApplyTransforms as ApplyTransforms
from niworkflows.interfaces import SimpleBeforeAfter
from ..interfaces import DerivativesDataSink


def init_anat_norm_wf(
    debug,
    omp_nthreads,
    reportlets_dir,
    template_list,
    template_specs=None,
):
    """
    An individual spatial normalization workflow using ``antsRegistration``.

    .. workflow ::
        :graph2use: orig
        :simple_form: yes

        from smriprep.workflows.norm import init_anat_norm_wf
        wf = init_anat_norm_wf(
            debug=False,
            omp_nthreads=1,
            reportlets_dir='.',
            template_list=['MNI152NLin2009cAsym', 'MNI152NLin6Asym'],
        )

    **Parameters**

        debug : bool
            Apply sloppy arguments to speed up processing. Use with caution,
            registration processes will be very inaccurate.
        omp_nthreads : int
            Maximum number of threads an individual process may use.
        reportlets_dir : str
            Directory in which to save reportlets.
        template_list : list of str
            List of TemplateFlow identifiers (e.g. ``MNI152NLin6Asym``) that
            specifies the target template for spatial normalization. In the
            future, this parameter should accept also paths to custom/private
            templates with TemplateFlow's organization.

    **Inputs**

        moving_image
            The input image that will be normalized to standard space.
        moving_mask
            A precise brain mask separating skull/skin/fat from brain
            structures.
        moving_segmentation
            A brain tissue segmentation of the ``moving_image``.
        moving_tpms
            tissue probability maps (TPMs) corresponding to the
            ``moving_segmentation``.
        lesion_mask
            (optional) A mask to exclude regions from the cost-function
            input domain to enable standardization of lesioned brains.
        orig_t1w
            The original T1w image from the BIDS structure.

    **Outputs**

        warped
            The T1w after spatial normalization, in template space.
        forward_transform
            The T1w-to-template transform.
        reverse_transform
            The template-to-T1w transform.
        tpl_mask
            The ``moving_mask`` in template space (matches ``warped`` output).
        tpl_seg
            The ``moving_segmentation`` in template space (matches ``warped``
            output).
        tpl_tpms
            The ``moving_tpms`` in template space (matches ``warped`` output).
        template
            The input parameter ``template`` for further use in nodes depending
            on this
            workflow.

    """

    if not isinstance(template_list, (list, tuple)):
        template_list = [template_list]

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

    if not template_specs:
        template_specs = [{}] * len(template_list)

    if len(template_list) != len(template_specs):
        raise RuntimeError('Number of templates (%d) doesn\'t match the number of specs '
                           '(%d) provided.' % (len(template_list), len(template_specs)))

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
    out_fields = ['warped', 'forward_transform', 'reverse_transform',
                  'tpl_mask', 'tpl_seg', 'tpl_tpms', 'template']
    poutputnode = pe.Node(niu.IdentityInterface(fields=out_fields), name='poutputnode')

    tpl_specs = pe.Node(niu.Function(function=_select_specs),
                        name='tpl_specs', run_without_submitting=True)
    tpl_specs.inputs.template_list = template_list
    tpl_specs.inputs.template_specs = template_specs

    tpl_select = pe.Node(niu.Function(function=_get_template),
                         name='tpl_select', run_without_submitting=True)

    # With the improvements from poldracklab/niworkflows#342 this truncation is now necessary
    trunc_mov = pe.Node(ImageMath(operation='TruncateImageIntensity', op2='0.01 0.999 256'),
                        name='trunc_mov')

    registration = pe.Node(RobustMNINormalization(
        float=True, flavor=['precise', 'testing'][debug],
    ), name='registration', n_procs=omp_nthreads, mem_gb=2)

    # Resample T1w-space inputs
    tpl_moving = pe.Node(ApplyTransforms(
        dimension=3, default_value=0, float=True,
        interpolation='LanczosWindowedSinc'), name='tpl_moving')
    tpl_mask = pe.Node(ApplyTransforms(dimension=3, default_value=0, float=True,
                                       interpolation='MultiLabel'), name='tpl_mask')

    tpl_seg = pe.Node(ApplyTransforms(dimension=3, default_value=0, float=True,
                                      interpolation='MultiLabel'), name='tpl_seg')

    tpl_tpms = pe.MapNode(ApplyTransforms(dimension=3, default_value=0, float=True,
                                          interpolation='Gaussian'),
                          iterfield=['input_image'], name='tpl_tpms')

    workflow.connect([
        (inputnode, tpl_specs, [('template', 'template')]),
        (inputnode, tpl_select, [('template', 'template')]),
        (inputnode, registration, [('template', 'template')]),
        (inputnode, trunc_mov, [('moving_image', 'op1')]),
        (inputnode, registration, [
            ('moving_mask', 'moving_mask'),
            ('lesion_mask', 'lesion_mask')]),
        (inputnode, tpl_moving, [('moving_image', 'input_image')]),
        (inputnode, tpl_mask, [('moving_mask', 'input_image')]),
        (tpl_specs, tpl_select, [('out', 'template_spec')]),
        (tpl_specs, registration, [(('out', _drop_res), 'template_spec')]),
        (tpl_select, tpl_moving, [('out', 'reference_image')]),
        (tpl_select, tpl_mask, [('out', 'reference_image')]),
        (tpl_select, tpl_seg, [('out', 'reference_image')]),
        (tpl_select, tpl_tpms, [('out', 'reference_image')]),
        (trunc_mov, registration, [
            ('output_image', 'moving_image')]),
        (registration, tpl_moving, [('composite_transform', 'transforms')]),
        (registration, tpl_mask, [('composite_transform', 'transforms')]),
        (inputnode, tpl_seg, [('moving_segmentation', 'input_image')]),
        (registration, tpl_seg, [('composite_transform', 'transforms')]),
        (inputnode, tpl_tpms, [('moving_tpms', 'input_image')]),
        (registration, tpl_tpms, [('composite_transform', 'transforms')]),
        (registration, poutputnode, [
            ('composite_transform', 'forward_transform'),
            ('inverse_composite_transform', 'reverse_transform')]),
        (tpl_moving, poutputnode, [('output_image', 'warped')]),
        (tpl_mask, poutputnode, [('output_image', 'tpl_mask')]),
        (tpl_seg, poutputnode, [('output_image', 'tpl_seg')]),
        (tpl_tpms, poutputnode, [('output_image', 'tpl_tpms')]),
        (inputnode, poutputnode, [('template', 'template')]),
    ])

    # Generate and store report
    msk_select = pe.Node(niu.Function(
        function=_get_template, input_names=['template', 'template_spec',
                                             'suffix', 'desc']),
        name='msk_select', run_without_submitting=True)
    msk_select.inputs.desc = 'brain'
    msk_select.inputs.suffix = 'mask'

    norm_msk = pe.Node(niu.Function(
        function=_rpt_masks, output_names=['before', 'after']),
        name='norm_msk')
    norm_rpt = pe.Node(SimpleBeforeAfter(), name='norm_rpt', mem_gb=0.1)
    norm_rpt.inputs.after_label = 'Participant'  # after

    ds_t1_2_tpl_report = pe.Node(
        DerivativesDataSink(base_directory=reportlets_dir, keep_dtype=True),
        name='ds_t1_2_tpl_report', run_without_submitting=True)

    workflow.connect([
        (inputnode, msk_select, [('template', 'template')]),
        (inputnode, norm_rpt, [('template', 'before_label')]),
        (tpl_specs, msk_select, [('out', 'template_spec')]),
        (msk_select, norm_msk, [('out', 'mask_file')]),
        (tpl_select, norm_msk, [('out', 'before')]),
        (tpl_moving, norm_msk, [('output_image', 'after')]),
        (norm_msk, norm_rpt, [('before', 'before'),
                              ('after', 'after')]),
        (inputnode, ds_t1_2_tpl_report, [
            ('template', 'space'),
            ('orig_t1w', 'source_file')]),
        (norm_rpt, ds_t1_2_tpl_report, [('out_report', 'in_file')]),
    ])

    # Provide synchronized output
    outputnode = pe.JoinNode(niu.IdentityInterface(fields=out_fields),
                             name='outputnode', joinsource='inputnode')
    workflow.connect([
        (poutputnode, outputnode, [(f, f) for f in out_fields]),
    ])

    return workflow


def _rpt_masks(mask_file, before, after):
    from os.path import abspath
    import nibabel as nb
    msk = nb.load(mask_file).get_fdata() > 0
    bnii = nb.load(before)
    nb.Nifti1Image(bnii.get_fdata() * msk,
                   bnii.affine, bnii.header).to_filename('before.nii.gz')
    anii = nb.load(after)
    nb.Nifti1Image(anii.get_fdata() * msk,
                   anii.affine, anii.header).to_filename('after.nii.gz')
    return abspath('before.nii.gz'), abspath('after.nii.gz')


def _select_specs(template, template_list, template_specs):
    return template_specs[template_list.index(template)]


def _get_template(template, template_spec, suffix='T1w', desc=None):
    from niworkflows.utils.misc import get_template_specs
    template_spec['suffix'] = suffix
    template_spec['desc'] = desc
    return get_template_specs(template, template_spec=template_spec)[0]


def _drop_res(in_dict):
    in_dict.pop('res', None)
    in_dict.pop('resoluton', None)
    return in_dict

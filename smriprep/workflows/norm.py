# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
"""
Spatial normalization workflows.

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
    Build an individual spatial normalization workflow using ``antsRegistration``.

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

        standardized
            The T1w after spatial normalization, in template space.
        anat2std_xfm
            The T1w-to-template transform.
        std2anat_xfm
            The template-to-T1w transform.
        std_mask
            The ``moving_mask`` in template space (matches ``standardized`` output).
        std_dseg
            The ``moving_segmentation`` in template space (matches ``standardized``
            output).
        std_tpms
            The ``moving_tpms`` in template space (matches ``standardized`` output).
        template
            The input parameter ``template`` for further use in nodes depending
            on this
            workflow.

    """
    if not isinstance(template_list, (list, tuple)):
        template_list = [template_list]

    templateflow = templates()
    missing_tpls = [template for template in template_list if template not in templateflow]
    if missing_tpls:
        raise ValueError("""\
One or more templates were not found (%s). Please make sure TemplateFlow is \
correctly installed and contains the given template identifiers.""" % ', '.join(missing_tpls))

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
    out_fields = ['standardized', 'anat2std_xfm', 'std2anat_xfm',
                  'std_mask', 'std_dseg', 'std_tpms', 'template']
    poutputnode = pe.Node(niu.IdentityInterface(fields=out_fields), name='poutputnode')

    tpl_specs = pe.Node(niu.Function(
        function=_select_specs,
        input_names=['template', 'template_list', 'template_specs', 'force_res']),
        name='tpl_specs', run_without_submitting=True)
    tpl_specs.inputs.template_list = template_list
    tpl_specs.inputs.template_specs = template_specs
    tpl_specs.inputs.force_res = 1

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
    std_mask = pe.Node(ApplyTransforms(dimension=3, default_value=0, float=True,
                                       interpolation='MultiLabel'), name='std_mask')

    std_dseg = pe.Node(ApplyTransforms(dimension=3, default_value=0, float=True,
                                       interpolation='MultiLabel'), name='std_dseg')

    std_tpms = pe.MapNode(ApplyTransforms(dimension=3, default_value=0, float=True,
                                          interpolation='Gaussian'),
                          iterfield=['input_image'], name='std_tpms')

    workflow.connect([
        (inputnode, tpl_specs, [('template', 'template')]),
        (inputnode, tpl_select, [('template', 'template')]),
        (inputnode, registration, [('template', 'template')]),
        (inputnode, trunc_mov, [('moving_image', 'op1')]),
        (inputnode, registration, [
            ('moving_mask', 'moving_mask'),
            ('lesion_mask', 'lesion_mask')]),
        (inputnode, tpl_moving, [('moving_image', 'input_image')]),
        (inputnode, std_mask, [('moving_mask', 'input_image')]),
        (tpl_specs, tpl_select, [('out', 'template_spec')]),
        (tpl_specs, registration, [(('out', _drop_res), 'template_spec')]),
        (tpl_select, tpl_moving, [('out', 'reference_image')]),
        (tpl_select, std_mask, [('out', 'reference_image')]),
        (tpl_select, std_dseg, [('out', 'reference_image')]),
        (tpl_select, std_tpms, [('out', 'reference_image')]),
        (trunc_mov, registration, [
            ('output_image', 'moving_image')]),
        (registration, tpl_moving, [('composite_transform', 'transforms')]),
        (registration, std_mask, [('composite_transform', 'transforms')]),
        (inputnode, std_dseg, [('moving_segmentation', 'input_image')]),
        (registration, std_dseg, [('composite_transform', 'transforms')]),
        (inputnode, std_tpms, [('moving_tpms', 'input_image')]),
        (registration, std_tpms, [('composite_transform', 'transforms')]),
        (registration, poutputnode, [
            ('composite_transform', 'anat2std_xfm'),
            ('inverse_composite_transform', 'std2anat_xfm')]),
        (tpl_moving, poutputnode, [('output_image', 'standardized')]),
        (std_mask, poutputnode, [('output_image', 'std_mask')]),
        (std_dseg, poutputnode, [('output_image', 'std_dseg')]),
        (std_tpms, poutputnode, [('output_image', 'std_tpms')]),
        (inputnode, poutputnode, [('template', 'template')]),
    ])

    # Generate and store report
    msk_select = pe.Node(niu.Function(
        function=_get_template,
        input_names=['template', 'template_spec', 'suffix', 'desc']),
        name='msk_select', run_without_submitting=True)
    msk_select.inputs.desc = 'brain'
    msk_select.inputs.suffix = 'mask'

    norm_msk = pe.Node(niu.Function(
        function=_rpt_masks, output_names=['before', 'after'],
        input_names=['mask_file', 'before', 'after', 'after_mask']),
        name='norm_msk')
    norm_rpt = pe.Node(SimpleBeforeAfter(), name='norm_rpt', mem_gb=0.1)
    norm_rpt.inputs.after_label = 'Participant'  # after

    ds_std_t1w_report = pe.Node(
        DerivativesDataSink(base_directory=reportlets_dir, suffix='T1w'),
        name='ds_std_t1w_report', run_without_submitting=True)

    workflow.connect([
        (inputnode, msk_select, [('template', 'template')]),
        (inputnode, norm_rpt, [('template', 'before_label')]),
        (std_mask, norm_msk, [('output_image', 'after_mask')]),
        (tpl_specs, msk_select, [('out', 'template_spec')]),
        (msk_select, norm_msk, [('out', 'mask_file')]),
        (tpl_select, norm_msk, [('out', 'before')]),
        (tpl_moving, norm_msk, [('output_image', 'after')]),
        (norm_msk, norm_rpt, [('before', 'before'),
                              ('after', 'after')]),
        (inputnode, ds_std_t1w_report, [
            ('template', 'space'),
            ('orig_t1w', 'source_file')]),
        (norm_rpt, ds_std_t1w_report, [('out_report', 'in_file')]),
    ])

    # Provide synchronized output
    outputnode = pe.JoinNode(niu.IdentityInterface(fields=out_fields),
                             name='outputnode', joinsource='inputnode')
    workflow.connect([
        (poutputnode, outputnode, [(f, f) for f in out_fields]),
    ])

    return workflow


def _rpt_masks(mask_file, before, after, after_mask=None):
    from os.path import abspath
    import nibabel as nb
    msk = nb.load(mask_file).get_fdata() > 0
    bnii = nb.load(before)
    nb.Nifti1Image(bnii.get_fdata() * msk,
                   bnii.affine, bnii.header).to_filename('before.nii.gz')
    if after_mask is not None:
        msk = nb.load(after_mask).get_fdata() > 0

    anii = nb.load(after)
    nb.Nifti1Image(anii.get_fdata() * msk,
                   anii.affine, anii.header).to_filename('after.nii.gz')
    return abspath('before.nii.gz'), abspath('after.nii.gz')


def _select_specs(template, template_list, template_specs, force_res=None):
    out_spec = template_specs[template_list.index(template)]
    if force_res is not None:
        out_spec.pop('res', None)
        out_spec.pop('resoluton', None)
        out_spec['res'] = force_res

    return out_spec


def _get_template(template, template_spec, suffix='T1w', desc=None):
    from niworkflows.utils.misc import get_template_specs
    template_spec['suffix'] = suffix
    template_spec['desc'] = desc
    return get_template_specs(template, template_spec=template_spec)[0]


def _drop_res(in_dict):
    in_dict.pop('res', None)
    in_dict.pop('resoluton', None)
    return in_dict

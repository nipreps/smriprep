# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
"""Writting outputs."""
from nipype.pipeline import engine as pe
from nipype.interfaces import utility as niu
from niworkflows.engine.workflows import LiterateWorkflow as Workflow
from niworkflows.utils.misc import fix_multi_T1w_source_name
from niworkflows.interfaces.surf import GiftiNameSource
from niworkflows.interfaces.freesurfer import PatchedLTAConvert as LTAConvert

from ..interfaces import DerivativesDataSink


def init_anat_reports_wf(reportlets_dir, freesurfer,
                         name='anat_reports_wf'):
    """Set up a battery of datasinks to store reports in the right location."""
    from niworkflows.interfaces import SimpleBeforeAfter
    from niworkflows.interfaces.masks import ROIsPlot
    from ..interfaces.templateflow import TemplateFlowSelect

    workflow = Workflow(name=name)

    inputfields = ['source_file', 't1w_conform_report',
                   't1w_preproc', 't1w_dseg', 't1w_mask',
                   'template', 'template_spec', 'std_t1w', 'std_mask',
                   'subject_id', 'subjects_dir']
    inputnode = pe.Node(niu.IdentityInterface(fields=inputfields),
                        name='inputnode')

    seg_rpt = pe.Node(ROIsPlot(colors=['magenta', 'b'], levels=[1.5, 2.5]),
                      name='seg_rpt')

    ds_t1w_conform_report = pe.Node(
        DerivativesDataSink(base_directory=reportlets_dir, desc='conform', keep_dtype=True),
        name='ds_t1w_conform_report', run_without_submitting=True)

    ds_t1w_dseg_mask_report = pe.Node(
        DerivativesDataSink(base_directory=reportlets_dir, suffix='dseg'),
        name='ds_t1w_dseg_mask_report', run_without_submitting=True)

    workflow.connect([
        (inputnode, ds_t1w_conform_report, [('source_file', 'source_file'),
                                            ('t1w_conform_report', 'in_file')]),
        (inputnode, ds_t1w_dseg_mask_report, [('source_file', 'source_file')]),
        (inputnode, seg_rpt, [('t1w_preproc', 'in_file'),
                              ('t1w_mask', 'in_mask'),
                              ('t1w_dseg', 'in_rois')]),
        (seg_rpt, ds_t1w_dseg_mask_report, [('out_report', 'in_file')]),

    ])

    # Generate reportlets showing spatial normalization
    tf_select = pe.Node(TemplateFlowSelect(resolution=1),
                        name='tf_select', run_without_submitting=True)
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
        (inputnode, tf_select, [('template', 'template'),
                                ('template_spec', 'template_spec')]),
        (inputnode, norm_rpt, [('template', 'before_label')]),
        (inputnode, norm_msk, [('std_t1w', 'after'),
                               ('std_mask', 'after_mask')]),
        (tf_select, norm_msk, [('t1w_file', 'before'),
                               ('brain_mask', 'mask_file')]),
        (norm_msk, norm_rpt, [('before', 'before'),
                              ('after', 'after')]),
        (inputnode, ds_std_t1w_report, [
            ('template', 'space'),
            ('source_file', 'source_file')]),
        (norm_rpt, ds_std_t1w_report, [('out_report', 'in_file')]),
    ])

    if freesurfer:
        from ..interfaces.reports import FSSurfaceReport
        recon_report = pe.Node(FSSurfaceReport(), name='recon_report')
        recon_report.interface._always_run = True

        ds_recon_report = pe.Node(
            DerivativesDataSink(base_directory=reportlets_dir, desc='reconall', keep_dtype=True),
            name='ds_recon_report', run_without_submitting=True)
        workflow.connect([
            (inputnode, recon_report, [('subjects_dir', 'subjects_dir'),
                                       ('subject_id', 'subject_id')]),
            (recon_report, ds_recon_report, [('out_report', 'in_file')]),
            (inputnode, ds_recon_report, [('source_file', 'source_file')])
        ])

    return workflow


def init_anat_derivatives_wf(bids_root, freesurfer, num_t1w, output_dir,
                             name='anat_derivatives_wf'):
    """Set up a battery of datasinks to store derivatives in the right location."""
    workflow = Workflow(name=name)

    inputnode = pe.Node(
        niu.IdentityInterface(
            fields=['template', 'source_files', 't1w_ref_xfms',
                    't1w_preproc', 't1w_mask', 't1w_dseg', 't1w_tpms',
                    'anat2std_xfm', 'std2anat_xfm',
                    'std_t1w', 'std_mask', 'std_dseg', 'std_tpms',
                    't1w2fsnative_xfm', 'fsnative2t1w_xfm', 'surfaces',
                    't1w_fs_aseg', 't1w_fs_aparc']),
        name='inputnode')

    t1w_name = pe.Node(niu.Function(function=fix_multi_T1w_source_name), name='t1w_name')
    raw_sources = pe.Node(niu.Function(function=_bids_relative), name='raw_sources')
    raw_sources.inputs.bids_root = bids_root

    ds_t1w_preproc = pe.Node(
        DerivativesDataSink(base_directory=output_dir, desc='preproc', keep_dtype=True,
                            compress=True),
        name='ds_t1w_preproc', run_without_submitting=True)
    ds_t1w_preproc.inputs.SkullStripped = False

    ds_t1w_mask = pe.Node(
        DerivativesDataSink(base_directory=output_dir, desc='brain', suffix='mask',
                            compress=True),
        name='ds_t1w_mask', run_without_submitting=True)
    ds_t1w_mask.inputs.Type = 'Brain'

    lut_t1w_dseg = pe.Node(niu.Function(function=_apply_default_bids_lut),
                           name='lut_t1w_dseg')
    ds_t1w_dseg = pe.Node(
        DerivativesDataSink(base_directory=output_dir, suffix='dseg',
                            compress=True),
        name='ds_t1w_dseg', run_without_submitting=True)

    ds_t1w_tpms = pe.Node(
        DerivativesDataSink(base_directory=output_dir,
                            suffix='probseg', compress=True),
        name='ds_t1w_tpms', run_without_submitting=True)
    ds_t1w_tpms.inputs.extra_values = ['label-CSF', 'label-GM', 'label-WM']

    ds_t1w_tpl = pe.Node(
        DerivativesDataSink(base_directory=output_dir, desc='preproc', keep_dtype=True,
                            compress=True),
        name='ds_t1w_tpl', run_without_submitting=True)
    ds_t1w_tpl.inputs.SkullStripped = True

    ds_std_mask = pe.Node(
        DerivativesDataSink(base_directory=output_dir, desc='brain', suffix='mask',
                            compress=True),
        name='ds_std_mask', run_without_submitting=True)
    ds_std_mask.inputs.Type = 'Brain'

    lut_std_dseg = pe.Node(niu.Function(function=_apply_default_bids_lut),
                           name='lut_std_dseg')
    ds_std_dseg = pe.Node(
        DerivativesDataSink(base_directory=output_dir, suffix='dseg',
                            compress=True),
        name='ds_std_dseg', run_without_submitting=True)

    ds_std_tpms = pe.Node(
        DerivativesDataSink(base_directory=output_dir, suffix='probseg',
                            compress=True),
        name='ds_std_tpms', run_without_submitting=True)
    ds_std_tpms.inputs.extra_values = ['label-CSF', 'label-GM', 'label-WM']

    # Transforms
    ds_t1w_tpl_inv_warp = pe.Node(
        DerivativesDataSink(base_directory=output_dir, allowed_entities=['from', 'to', 'mode'],
                            to='T1w', mode='image', suffix='xfm'),
        name='ds_t1w_tpl_inv_warp', run_without_submitting=True)

    ds_t1w_tpl_warp = pe.Node(
        DerivativesDataSink(base_directory=output_dir, allowed_entities=['from', 'to', 'mode'],
                            mode='image', suffix='xfm', **{'from': 'T1w'}),
        name='ds_t1w_tpl_warp', run_without_submitting=True)

    workflow.connect([
        (inputnode, t1w_name, [('source_files', 'in_files')]),
        (inputnode, raw_sources, [('source_files', 'in_files')]),
        (inputnode, ds_t1w_preproc, [('t1w_preproc', 'in_file')]),
        (inputnode, ds_t1w_mask, [('t1w_mask', 'in_file')]),
        (inputnode, lut_t1w_dseg, [('t1w_dseg', 'in_file')]),
        (inputnode, ds_t1w_tpms, [('t1w_tpms', 'in_file')]),
        (lut_t1w_dseg, ds_t1w_dseg, [('out', 'in_file')]),
        (t1w_name, ds_t1w_preproc, [('out', 'source_file')]),
        (t1w_name, ds_t1w_mask, [('out', 'source_file')]),
        (t1w_name, ds_t1w_dseg, [('out', 'source_file')]),
        (t1w_name, ds_t1w_tpms, [('out', 'source_file')]),
        (raw_sources, ds_t1w_mask, [('out', 'RawSources')]),
        # Template
        (inputnode, ds_t1w_tpl_warp, [
            ('anat2std_xfm', 'in_file'),
            ('template', 'to')]),
        (inputnode, ds_t1w_tpl_inv_warp, [
            ('std2anat_xfm', 'in_file'),
            ('template', 'from')]),
        (inputnode, ds_t1w_tpl, [
            ('std_t1w', 'in_file'),
            ('template', 'space')]),
        (inputnode, ds_std_mask, [
            ('std_mask', 'in_file'),
            ('template', 'space'),
            (('template', _rawsources), 'RawSources')]),
        (inputnode, ds_std_dseg, [('template', 'space')]),
        (inputnode, lut_std_dseg, [('std_dseg', 'in_file')]),
        (lut_std_dseg, ds_std_dseg, [('out', 'in_file')]),
        (inputnode, ds_std_tpms, [
            ('std_tpms', 'in_file'),
            ('template', 'space')]),
        (t1w_name, ds_t1w_tpl_warp, [('out', 'source_file')]),
        (t1w_name, ds_t1w_tpl_inv_warp, [('out', 'source_file')]),
        (t1w_name, ds_t1w_tpl, [('out', 'source_file')]),
        (t1w_name, ds_std_mask, [('out', 'source_file')]),
        (t1w_name, ds_std_dseg, [('out', 'source_file')]),
        (t1w_name, ds_std_tpms, [('out', 'source_file')]),
    ])

    if num_t1w > 1:
        # Please note the dictionary unpacking to provide the from argument.
        # It is necessary because from is a protected keyword (not allowed as argument name).
        ds_t1w_ref_xfms = pe.MapNode(
            DerivativesDataSink(base_directory=output_dir, allowed_entities=['from', 'to', 'mode'],
                                to='T1w', mode='image', suffix='xfm', **{'from': 'orig'}),
            iterfield=['source_file', 'in_file'],
            name='ds_t1w_ref_xfms', run_without_submitting=True)
        workflow.connect([
            (inputnode, ds_t1w_ref_xfms, [('source_files', 'source_file'),
                                          ('t1w_ref_xfms', 'in_file')]),
        ])

    if not freesurfer:
        return workflow

    # FS native space transforms
    lta2itk_fwd = pe.Node(LTAConvert(out_itk=True), name='lta2itk_fwd')
    lta2itk_inv = pe.Node(LTAConvert(out_itk=True), name='lta2itk_inv')
    ds_t1w_fsnative = pe.Node(
        DerivativesDataSink(base_directory=output_dir, allowed_entities=['from', 'to', 'mode'],
                            mode='image', to='fsnative', suffix='xfm', **{'from': 'T1w'}),
        name='ds_t1w_fsnative', run_without_submitting=True)
    ds_fsnative_t1w = pe.Node(
        DerivativesDataSink(base_directory=output_dir, allowed_entities=['from', 'to', 'mode'],
                            mode='image', to='T1w', suffix='xfm', **{'from': 'fsnative'}),
        name='ds_fsnative_t1w', run_without_submitting=True)
    # Surfaces
    name_surfs = pe.MapNode(GiftiNameSource(
        pattern=r'(?P<LR>[lr])h.(?P<surf>.+)_converted.gii',
        template='hemi-{LR}_{surf}.surf'),
        iterfield='in_file', name='name_surfs', run_without_submitting=True)
    ds_surfs = pe.MapNode(
        DerivativesDataSink(base_directory=output_dir),
        iterfield=['in_file', 'suffix'], name='ds_surfs', run_without_submitting=True)
    # Parcellations
    ds_t1w_fsaseg = pe.Node(
        DerivativesDataSink(base_directory=output_dir, desc='aseg', suffix='dseg',
                            compress=True),
        name='ds_t1w_fsaseg', run_without_submitting=True)
    ds_t1w_fsparc = pe.Node(
        DerivativesDataSink(base_directory=output_dir, desc='aparcaseg', suffix='dseg',
                            compress=True),
        name='ds_t1w_fsparc', run_without_submitting=True)

    workflow.connect([
        (inputnode, lta2itk_fwd, [('t1w2fsnative_xfm', 'in_lta')]),
        (inputnode, lta2itk_inv, [('fsnative2t1w_xfm', 'in_lta')]),
        (t1w_name, ds_t1w_fsnative, [('out', 'source_file')]),
        (lta2itk_fwd, ds_t1w_fsnative, [('out_itk', 'in_file')]),
        (t1w_name, ds_fsnative_t1w, [('out', 'source_file')]),
        (lta2itk_inv, ds_fsnative_t1w, [('out_itk', 'in_file')]),
        (inputnode, name_surfs, [('surfaces', 'in_file')]),
        (inputnode, ds_surfs, [('surfaces', 'in_file')]),
        (t1w_name, ds_surfs, [('out', 'source_file')]),
        (name_surfs, ds_surfs, [('out_name', 'suffix')]),
        (inputnode, ds_t1w_fsaseg, [('t1w_fs_aseg', 'in_file')]),
        (inputnode, ds_t1w_fsparc, [('t1w_fs_aparc', 'in_file')]),
        (t1w_name, ds_t1w_fsaseg, [('out', 'source_file')]),
        (t1w_name, ds_t1w_fsparc, [('out', 'source_file')]),
    ])

    return workflow


def _apply_default_bids_lut(in_file):
    import numpy as np
    import nibabel as nb
    from os import getcwd
    from nipype.utils.filemanip import fname_presuffix

    out_file = fname_presuffix(in_file, suffix='_lut', newpath=getcwd())
    lut = np.array([0, 3, 1, 2], dtype=int)

    segm = nb.load(in_file)
    segm.__class__(lut[segm.get_data().astype(int)],
                   segm.affine, segm.header).to_filename(out_file)

    return out_file


def _bids_relative(in_files, bids_root):
    from pathlib import Path
    if not isinstance(in_files, (list, tuple)):
        in_files = [in_files]
    in_files = [str(Path(p).relative_to(bids_root)) for p in in_files]
    return in_files


def _rawsources(template):
    if isinstance(template, tuple):
        template = template[0]
    return 'tpl-{0}/tpl-{0}_desc-brain_mask.nii.gz'.format(template)


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

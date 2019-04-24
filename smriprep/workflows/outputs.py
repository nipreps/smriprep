# -*- coding: utf-8 -*-
# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
"""
Writting outputs
----------------

.. autofunction:: init_anat_reports_wf
.. autofunction:: init_anat_derivatives_wf

"""
from nipype.pipeline import engine as pe
from nipype.interfaces import utility as niu
from niworkflows.engine.workflows import LiterateWorkflow as Workflow
from niworkflows.utils.misc import fix_multi_T1w_source_name
from niworkflows.interfaces.surf import GiftiNameSource
from niworkflows.interfaces.freesurfer import PatchedLTAConvert as LTAConvert

from ..interfaces import DerivativesDataSink


def init_anat_reports_wf(reportlets_dir, freesurfer,
                         name='anat_reports_wf'):
    """
    Set up a battery of datasinks to store reports in the right location
    """
    workflow = Workflow(name=name)

    inputnode = pe.Node(
        niu.IdentityInterface(
            fields=['source_file', 't1_conform_report', 'seg_report', 'recon_report']),
        name='inputnode')

    ds_t1_conform_report = pe.Node(
        DerivativesDataSink(base_directory=reportlets_dir, desc='conform', keep_dtype=True),
        name='ds_t1_conform_report', run_without_submitting=True)

    ds_t1_seg_mask_report = pe.Node(
        DerivativesDataSink(base_directory=reportlets_dir, suffix='dseg'),
        name='ds_t1_seg_mask_report', run_without_submitting=True)

    workflow.connect([
        (inputnode, ds_t1_conform_report, [('source_file', 'source_file'),
                                           ('t1_conform_report', 'in_file')]),
        (inputnode, ds_t1_seg_mask_report, [('source_file', 'source_file'),
                                            ('seg_report', 'in_file')]),
    ])

    if freesurfer:
        ds_recon_report = pe.Node(
            DerivativesDataSink(base_directory=reportlets_dir, desc='reconall', keep_dtype=True),
            name='ds_recon_report', run_without_submitting=True)
        workflow.connect([
            (inputnode, ds_recon_report, [('source_file', 'source_file'),
                                          ('recon_report', 'in_file')])
        ])

    return workflow


def init_anat_derivatives_wf(bids_root, freesurfer, output_dir,
                             name='anat_derivatives_wf'):
    """
    Set up a battery of datasinks to store derivatives in the right location
    """
    workflow = Workflow(name=name)

    inputnode = pe.Node(
        niu.IdentityInterface(
            fields=['template', 'source_files', 't1_template_transforms',
                    't1_preproc', 't1_mask', 't1_seg', 't1_tpms',
                    't1_2_tpl_forward_transform', 't1_2_tpl_reverse_transform',
                    't1_2_tpl', 'tpl_mask', 'tpl_seg', 'tpl_tpms',
                    't1_2_fsnative_forward_transform', 'surfaces',
                    't1_fs_aseg', 't1_fs_aparc']),
        name='inputnode')

    t1_name = pe.Node(niu.Function(function=fix_multi_T1w_source_name), name='t1_name')
    raw_sources = pe.Node(niu.Function(function=_bids_relative), name='raw_sources')
    raw_sources.inputs.bids_root = bids_root

    ds_t1_preproc = pe.Node(
        DerivativesDataSink(base_directory=output_dir, desc='preproc', keep_dtype=True),
        name='ds_t1_preproc', run_without_submitting=True)
    ds_t1_preproc.inputs.SkullStripped = False

    ds_t1_mask = pe.Node(
        DerivativesDataSink(base_directory=output_dir, desc='brain', suffix='mask'),
        name='ds_t1_mask', run_without_submitting=True)
    ds_t1_mask.inputs.Type = 'Brain'

    lut_t1_seg = pe.Node(niu.Function(function=_apply_default_bids_lut),
                         name='lut_t1_seg')
    ds_t1_seg = pe.Node(
        DerivativesDataSink(base_directory=output_dir, suffix='dseg'),
        name='ds_t1_seg', run_without_submitting=True)

    ds_t1_tpms = pe.Node(
        DerivativesDataSink(base_directory=output_dir,
                            suffix='probseg'),
        name='ds_t1_tpms', run_without_submitting=True)
    ds_t1_tpms.inputs.extra_values = ['label-CSF', 'label-GM', 'label-WM']

    ds_t1_tpl = pe.Node(
        DerivativesDataSink(base_directory=output_dir, desc='preproc', keep_dtype=True),
        name='ds_t1_tpl', run_without_submitting=True)
    ds_t1_tpl.inputs.SkullStripped = True

    ds_tpl_mask = pe.Node(
        DerivativesDataSink(base_directory=output_dir, desc='brain', suffix='mask'),
        name='ds_tpl_mask', run_without_submitting=True)
    ds_tpl_mask.inputs.Type = 'Brain'

    lut_tpl_seg = pe.Node(niu.Function(function=_apply_default_bids_lut),
                          name='lut_tpl_seg')
    ds_tpl_seg = pe.Node(
        DerivativesDataSink(base_directory=output_dir, suffix='dseg'),
        name='ds_tpl_seg', run_without_submitting=True)

    ds_tpl_tpms = pe.Node(
        DerivativesDataSink(base_directory=output_dir, suffix='probseg'),
        name='ds_tpl_tpms', run_without_submitting=True)
    ds_tpl_tpms.inputs.extra_values = ['label-CSF', 'label-GM', 'label-WM']

    # Transforms
    ds_t1_tpl_inv_warp = pe.Node(
        DerivativesDataSink(base_directory=output_dir, allowed_entities=['from', 'to', 'mode'],
                            to='T1w', mode='image', suffix='xfm'),
        name='ds_t1_tpl_inv_warp', run_without_submitting=True)

    # Please note the dictionary unpacking to provide the from argument.
    # It is necessary because from is a protected keyword (not allowed as argument name).
    ds_t1_template_transforms = pe.MapNode(
        DerivativesDataSink(base_directory=output_dir, allowed_entities=['from', 'to', 'mode'],
                            to='T1w', mode='image', suffix='xfm', **{'from': 'orig'}),
        iterfield=['source_file', 'in_file'],
        name='ds_t1_template_transforms', run_without_submitting=True)

    ds_t1_tpl_warp = pe.Node(
        DerivativesDataSink(base_directory=output_dir, allowed_entities=['from', 'to', 'mode'],
                            mode='image', suffix='xfm', **{'from': 'T1w'}),
        name='ds_t1_tpl_warp', run_without_submitting=True)

    lta_2_itk = pe.Node(LTAConvert(out_itk=True), name='lta_2_itk')

    ds_t1_fsnative = pe.Node(
        DerivativesDataSink(base_directory=output_dir, allowed_entities=['from', 'to', 'mode'],
                            mode='image', to='fsnative', suffix='xfm', **{'from': 'T1w'}),
        name='ds_t1_fsnative', run_without_submitting=True)

    name_surfs = pe.MapNode(GiftiNameSource(pattern=r'(?P<LR>[lr])h.(?P<surf>.+)_converted.gii',
                                            template='hemi-{LR}_{surf}.surf'),
                            iterfield='in_file',
                            name='name_surfs',
                            run_without_submitting=True)

    ds_surfs = pe.MapNode(
        DerivativesDataSink(base_directory=output_dir),
        iterfield=['in_file', 'suffix'], name='ds_surfs', run_without_submitting=True)

    workflow.connect([
        (inputnode, t1_name, [('source_files', 'in_files')]),
        (inputnode, raw_sources, [('source_files', 'in_files')]),
        (inputnode, ds_t1_template_transforms, [('source_files', 'source_file'),
                                                ('t1_template_transforms', 'in_file')]),
        (inputnode, ds_t1_preproc, [('t1_preproc', 'in_file')]),
        (inputnode, ds_t1_mask, [('t1_mask', 'in_file')]),
        (inputnode, lut_t1_seg, [('t1_seg', 'in_file')]),
        (inputnode, ds_t1_tpms, [('t1_tpms', 'in_file')]),
        (lut_t1_seg, ds_t1_seg, [('out', 'in_file')]),
        (t1_name, ds_t1_preproc, [('out', 'source_file')]),
        (t1_name, ds_t1_mask, [('out', 'source_file')]),
        (t1_name, ds_t1_seg, [('out', 'source_file')]),
        (t1_name, ds_t1_tpms, [('out', 'source_file')]),
        (raw_sources, ds_t1_mask, [('out', 'RawSources')]),
        # Template
        (inputnode, ds_t1_tpl_warp, [
            ('t1_2_tpl_forward_transform', 'in_file'),
            ('template', 'to')]),
        (inputnode, ds_t1_tpl_inv_warp, [
            ('t1_2_tpl_reverse_transform', 'in_file'),
            ('template', 'from')]),
        (inputnode, ds_t1_tpl, [
            ('t1_2_tpl', 'in_file'),
            ('template', 'space')]),
        (inputnode, ds_tpl_mask, [
            ('tpl_mask', 'in_file'),
            ('template', 'space'),
            (('template', _rawsources), 'RawSources')]),
        (inputnode, ds_tpl_seg, [('template', 'space')]),
        (inputnode, lut_tpl_seg, [('tpl_seg', 'in_file')]),
        (lut_tpl_seg, ds_tpl_seg, [('out', 'in_file')]),
        (inputnode, ds_tpl_tpms, [
            ('tpl_tpms', 'in_file'),
            ('template', 'space')]),
        (t1_name, ds_t1_tpl_warp, [('out', 'source_file')]),
        (t1_name, ds_t1_tpl_inv_warp, [('out', 'source_file')]),
        (t1_name, ds_t1_tpl, [('out', 'source_file')]),
        (t1_name, ds_tpl_mask, [('out', 'source_file')]),
        (t1_name, ds_tpl_seg, [('out', 'source_file')]),
        (t1_name, ds_tpl_tpms, [('out', 'source_file')]),
    ])

    if freesurfer:
        ds_t1_fsaseg = pe.Node(
            DerivativesDataSink(base_directory=output_dir, desc='aseg', suffix='dseg'),
            name='ds_t1_fsaseg', run_without_submitting=True)
        ds_t1_fsparc = pe.Node(
            DerivativesDataSink(base_directory=output_dir, desc='aparcaseg', suffix='dseg'),
            name='ds_t1_fsparc', run_without_submitting=True)
        ds_t1_fsparc = pe.Node(
            DerivativesDataSink(base_directory=output_dir, desc='aparcaseg', suffix='dseg'),
            name='ds_t1_fsparc', run_without_submitting=True)

        workflow.connect([
            (inputnode, lta_2_itk, [('t1_2_fsnative_forward_transform', 'in_lta')]),
            (t1_name, ds_t1_fsnative, [('out', 'source_file')]),
            (lta_2_itk, ds_t1_fsnative, [('out_itk', 'in_file')]),
            (inputnode, name_surfs, [('surfaces', 'in_file')]),
            (inputnode, ds_surfs, [('surfaces', 'in_file')]),
            (t1_name, ds_surfs, [('out', 'source_file')]),
            (name_surfs, ds_surfs, [('out_name', 'suffix')]),
            (inputnode, ds_t1_fsaseg, [('t1_fs_aseg', 'in_file')]),
            (inputnode, ds_t1_fsparc, [('t1_fs_aparc', 'in_file')]),
            (t1_name, ds_t1_fsaseg, [('out', 'source_file')]),
            (t1_name, ds_t1_fsparc, [('out', 'source_file')]),
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
    return 'tpl-{0}/tpl-{0}_desc-brain_mask.nii.gz'.format(template)

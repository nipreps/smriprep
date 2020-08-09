# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
"""Writing outputs."""
from nipype.pipeline import engine as pe
from nipype.interfaces import utility as niu
from niworkflows.engine.workflows import LiterateWorkflow as Workflow
from niworkflows.utils.misc import fix_multi_T1w_source_name

from ..interfaces import DerivativesDataSink

BIDS_TISSUE_ORDER = ("GM", "WM", "CSF")


def init_anat_reports_wf(*, freesurfer, output_dir,
                         name='anat_reports_wf'):
    """
    Set up a battery of datasinks to store reports in the right location.

    Parameters
    ----------
    freesurfer : :obj:`bool`
        FreeSurfer was enabled
    output_dir : :obj:`str`
        Directory in which to save derivatives
    name : :obj:`str`
        Workflow name (default: anat_reports_wf)

    Inputs
    ------
    source_file
        Input T1w image
    std_t1w
        T1w image resampled to standard space
    std_mask
        Mask of skull-stripped template
    subject_dir
        FreeSurfer SUBJECTS_DIR
    subject_id
        FreeSurfer subject ID
    t1w_conform_report
        Conformation report
    t1w_preproc
        The T1w reference map, which is calculated as the average of bias-corrected
        and preprocessed T1w images, defining the anatomical space.
    t1w_dseg
        Segmentation in T1w space
    t1w_mask
        Brain (binary) mask estimated by brain extraction.
    template
        Template space and specifications

    """
    from niworkflows.interfaces import SimpleBeforeAfter
    from niworkflows.interfaces.masks import ROIsPlot
    from ..interfaces.templateflow import TemplateFlowSelect

    workflow = Workflow(name=name)

    inputfields = ['source_file', 't1w_conform_report',
                   't1w_preproc', 't1w_dseg', 't1w_mask',
                   'template', 'std_t1w', 'std_mask',
                   'subject_id', 'subjects_dir']
    inputnode = pe.Node(niu.IdentityInterface(fields=inputfields),
                        name='inputnode')

    seg_rpt = pe.Node(ROIsPlot(colors=['b', 'magenta'], levels=[1.5, 2.5]),
                      name='seg_rpt')

    t1w_conform_check = pe.Node(niu.Function(
        function=_empty_report),
        name='t1w_conform_check', run_without_submitting=True)

    ds_t1w_conform_report = pe.Node(
        DerivativesDataSink(base_directory=output_dir, desc='conform', datatype="figures",
                            dismiss_entities=("session",)),
        name='ds_t1w_conform_report', run_without_submitting=True)

    ds_t1w_dseg_mask_report = pe.Node(
        DerivativesDataSink(base_directory=output_dir, suffix='dseg', datatype="figures",
                            dismiss_entities=("session",)),
        name='ds_t1w_dseg_mask_report', run_without_submitting=True)

    workflow.connect([
        (inputnode, t1w_conform_check, [('t1w_conform_report', 'in_file')]),
        (t1w_conform_check, ds_t1w_conform_report, [('out', 'in_file')]),
        (inputnode, ds_t1w_conform_report, [('source_file', 'source_file')]),
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
        DerivativesDataSink(base_directory=output_dir, suffix='T1w', datatype="figures",
                            dismiss_entities=("session",)),
        name='ds_std_t1w_report', run_without_submitting=True)

    workflow.connect([
        (inputnode, tf_select, [('template', 'template')]),
        (inputnode, norm_rpt, [('template', 'before_label')]),
        (inputnode, norm_msk, [('std_t1w', 'after'),
                               ('std_mask', 'after_mask')]),
        (tf_select, norm_msk, [('t1w_file', 'before'),
                               ('brain_mask', 'mask_file')]),
        (norm_msk, norm_rpt, [('before', 'before'),
                              ('after', 'after')]),
        (inputnode, ds_std_t1w_report, [
            (('template', _fmt_cohort), 'space'),
            ('source_file', 'source_file')]),
        (norm_rpt, ds_std_t1w_report, [('out_report', 'in_file')]),
    ])

    if freesurfer:
        from ..interfaces.reports import FSSurfaceReport
        recon_report = pe.Node(FSSurfaceReport(), name='recon_report')
        recon_report.interface._always_run = True

        ds_recon_report = pe.Node(
            DerivativesDataSink(
                base_directory=output_dir, desc='reconall', datatype="figures",
                dismiss_entities=("session",)),
            name='ds_recon_report', run_without_submitting=True)
        workflow.connect([
            (inputnode, recon_report, [('subjects_dir', 'subjects_dir'),
                                       ('subject_id', 'subject_id')]),
            (recon_report, ds_recon_report, [('out_report', 'in_file')]),
            (inputnode, ds_recon_report, [('source_file', 'source_file')])
        ])

    return workflow


def init_anat_derivatives_wf(*, bids_root, freesurfer, num_t1w, output_dir,
                             name='anat_derivatives_wf', tpm_labels=BIDS_TISSUE_ORDER):
    """
    Set up a battery of datasinks to store derivatives in the right location.

    Parameters
    ----------
    bids_root : :obj:`str`
        Root path of BIDS dataset
    freesurfer : :obj:`bool`
        FreeSurfer was enabled
    num_t1w : :obj:`int`
        Number of T1w images
    output_dir : :obj:`str`
        Directory in which to save derivatives
    name : :obj:`str`
        Workflow name (default: anat_derivatives_wf)
    tpm_labels : :obj:`tuple`
        Tissue probability maps in order

    Inputs
    ------
    template
        Template space and specifications
    source_files
        List of input T1w images
    t1w_ref_xfms
        List of affine transforms to realign input T1w images
    t1w_preproc
        The T1w reference map, which is calculated as the average of bias-corrected
        and preprocessed T1w images, defining the anatomical space.
    t1w_mask
        Mask of the ``t1w_preproc``
    t1w_dseg
        Segmentation in T1w space
    t1w_tpms
        Tissue probability maps in T1w space
    anat2std_xfm
        Nonlinear spatial transform to resample imaging data given in anatomical space
        into standard space.
    std2anat_xfm
        Inverse transform of ``anat2std_xfm``
    std_t1w
        T1w reference resampled in one or more standard spaces.
    std_mask
        Mask of skull-stripped template, in standard space
    std_dseg
        Segmentation, resampled into standard space
    std_tpms
        Tissue probability maps in standard space
    t1w2fsnative_xfm
        LTA-style affine matrix translating from T1w to
        FreeSurfer-conformed subject space
    fsnative2t1w_xfm
        LTA-style affine matrix translating from FreeSurfer-conformed
        subject space to T1w
    surfaces
        GIFTI surfaces (gray/white boundary, midthickness, pial, inflated)
    t1w_fs_aseg
        FreeSurfer's aseg segmentation, in native T1w space
    t1w_fs_aparc
        FreeSurfer's aparc+aseg segmentation, in native T1w space

    """
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

    t1w_name = pe.Node(niu.Function(
        function=fix_multi_T1w_source_name),
        name='t1w_name', run_without_submitting=True)
    raw_sources = pe.Node(niu.Function(function=_bids_relative), name='raw_sources')
    raw_sources.inputs.bids_root = bids_root

    ds_t1w_preproc = pe.Node(
        DerivativesDataSink(base_directory=output_dir, desc='preproc', compress=True,
                            dismiss_entities=("session",)),
        name='ds_t1w_preproc', run_without_submitting=True)
    ds_t1w_preproc.inputs.SkullStripped = False

    ds_t1w_mask = pe.Node(
        DerivativesDataSink(base_directory=output_dir, desc='brain', suffix='mask',
                            compress=True, dismiss_entities=("session",)),
        name='ds_t1w_mask', run_without_submitting=True)
    ds_t1w_mask.inputs.Type = 'Brain'

    ds_t1w_dseg = pe.Node(
        DerivativesDataSink(base_directory=output_dir, suffix='dseg', compress=True,
                            dismiss_entities=("session",)),
        name='ds_t1w_dseg', run_without_submitting=True)

    ds_t1w_tpms = pe.Node(
        DerivativesDataSink(base_directory=output_dir, suffix='probseg', compress=True,
                            dismiss_entities=("session",)),
        name='ds_t1w_tpms', run_without_submitting=True)
    ds_t1w_tpms.inputs.label = tpm_labels

    # Transforms
    ds_t1w_tpl_inv_warp = pe.Node(
        DerivativesDataSink(base_directory=output_dir, to='T1w', mode='image', suffix='xfm',
                            dismiss_entities=("session",)),
        name='ds_t1w_tpl_inv_warp', run_without_submitting=True)

    ds_t1w_tpl_warp = pe.Node(
        DerivativesDataSink(base_directory=output_dir, mode='image', suffix='xfm',
                            dismiss_entities=("session",), **{'from': 'T1w'}),
        name='ds_t1w_tpl_warp', run_without_submitting=True)

    workflow.connect([
        (inputnode, t1w_name, [('source_files', 'in_files')]),
        (inputnode, raw_sources, [('source_files', 'in_files')]),
        (inputnode, ds_t1w_preproc, [('t1w_preproc', 'in_file')]),
        (inputnode, ds_t1w_mask, [('t1w_mask', 'in_file')]),
        (inputnode, ds_t1w_tpms, [('t1w_tpms', 'in_file')]),
        (inputnode, ds_t1w_dseg, [('t1w_dseg', 'in_file')]),
        (t1w_name, ds_t1w_preproc, [('out', 'source_file')]),
        (t1w_name, ds_t1w_mask, [('out', 'source_file')]),
        (t1w_name, ds_t1w_dseg, [('out', 'source_file')]),
        (t1w_name, ds_t1w_tpms, [('out', 'source_file')]),
        (raw_sources, ds_t1w_mask, [('out', 'RawSources')]),
        # Template
        (inputnode, ds_t1w_tpl_warp, [
            ('anat2std_xfm', 'in_file'),
            (('template', _drop_cohort), 'to')]),
        (inputnode, ds_t1w_tpl_inv_warp, [
            ('std2anat_xfm', 'in_file'),
            (('template', _drop_cohort), 'from')]),
        (t1w_name, ds_t1w_tpl_warp, [('out', 'source_file')]),
        (t1w_name, ds_t1w_tpl_inv_warp, [('out', 'source_file')]),
    ])

    if num_t1w > 1:
        # Please note the dictionary unpacking to provide the from argument.
        # It is necessary because from is a protected keyword (not allowed as argument name).
        ds_t1w_ref_xfms = pe.MapNode(
            DerivativesDataSink(base_directory=output_dir, to='T1w', mode='image', suffix='xfm',
                                extension='txt', **{'from': 'orig'}),
            iterfield=['source_file', 'in_file'],
            name='ds_t1w_ref_xfms', run_without_submitting=True)
        workflow.connect([
            (inputnode, ds_t1w_ref_xfms, [('source_files', 'source_file'),
                                          ('t1w_ref_xfms', 'in_file')]),
        ])

    # Write derivatives in standard spaces specified by --output-spaces
    ds_t1w_tpl = pe.Node(
        DerivativesDataSink(base_directory=output_dir, desc='preproc', keep_dtype=True,
                            compress=True, dismiss_entities=("session",)),
        name='ds_t1w_tpl', run_without_submitting=True)
    ds_t1w_tpl.inputs.SkullStripped = True

    ds_std_mask = pe.Node(
        DerivativesDataSink(base_directory=output_dir, desc='brain', suffix='mask',
                            compress=True, dismiss_entities=("session",)),
        name='ds_std_mask', run_without_submitting=True)
    ds_std_mask.inputs.Type = 'Brain'

    ds_std_dseg = pe.Node(
        DerivativesDataSink(base_directory=output_dir, suffix='dseg',
                            compress=True, dismiss_entities=("session",)),
        name='ds_std_dseg', run_without_submitting=True)

    ds_std_tpms = pe.Node(
        DerivativesDataSink(base_directory=output_dir, suffix='probseg',
                            compress=True, dismiss_entities=("session",)),
        name='ds_std_tpms', run_without_submitting=True)

    # CRITICAL: the sequence of labels here (CSF-GM-WM) is that of the output of FSL-FAST
    #           (intensity mean, per tissue). This order HAS to be matched also by the ``tpms``
    #           output in the data/io_spec.json file.
    ds_std_tpms.inputs.label = tpm_labels
    workflow.connect([
        (inputnode, ds_t1w_tpl, [
            ('std_t1w', 'in_file'),
            (('template', _fmt_cohort), 'space')]),
        (inputnode, ds_std_mask, [
            ('std_mask', 'in_file'),
            (('template', _fmt_cohort), 'space'),
            (('template', _rawsources), 'RawSources')]),
        (inputnode, ds_std_dseg, [(('template', _fmt_cohort), 'space')]),
        (inputnode, ds_std_dseg, [('std_dseg', 'in_file')]),
        (inputnode, ds_std_tpms, [
            ('std_tpms', 'in_file'),
            (('template', _fmt_cohort), 'space')]),
        (t1w_name, ds_t1w_tpl, [('out', 'source_file')]),
        (t1w_name, ds_std_mask, [('out', 'source_file')]),
        (t1w_name, ds_std_dseg, [('out', 'source_file')]),
        (t1w_name, ds_std_tpms, [('out', 'source_file')]),
    ])

    if not freesurfer:
        return workflow

    from niworkflows.interfaces.nitransforms import ConcatenateXFMs
    from niworkflows.interfaces.surf import Path2BIDS

    # FS native space transforms
    lta2itk_fwd = pe.Node(ConcatenateXFMs(), name='lta2itk_fwd', run_without_submitting=True)
    lta2itk_inv = pe.Node(ConcatenateXFMs(), name='lta2itk_inv', run_without_submitting=True)
    ds_t1w_fsnative = pe.Node(
        DerivativesDataSink(base_directory=output_dir, mode='image', to='fsnative', suffix='xfm',
                            extension="txt", dismiss_entities=("session",), **{'from': 'T1w'}),
        name='ds_t1w_fsnative', run_without_submitting=True)
    ds_fsnative_t1w = pe.Node(
        DerivativesDataSink(base_directory=output_dir, mode='image', to='T1w', suffix='xfm',
                            extension="txt",
                            dismiss_entities=("session",), **{'from': 'fsnative'}),
        name='ds_fsnative_t1w', run_without_submitting=True)
    # Surfaces
    name_surfs = pe.MapNode(Path2BIDS(), iterfield='in_file', name='name_surfs',
                            run_without_submitting=True)
    ds_surfs = pe.MapNode(
        DerivativesDataSink(base_directory=output_dir, extension=".surf.gii",
                            dismiss_entities=("session",)),
        iterfield=['in_file', 'hemi', 'suffix'], name='ds_surfs', run_without_submitting=True)
    # Parcellations
    ds_t1w_fsaseg = pe.Node(
        DerivativesDataSink(base_directory=output_dir, desc='aseg', suffix='dseg',
                            compress=True, dismiss_entities=("session",)),
        name='ds_t1w_fsaseg', run_without_submitting=True)
    ds_t1w_fsparc = pe.Node(
        DerivativesDataSink(base_directory=output_dir, desc='aparcaseg', suffix='dseg',
                            compress=True, dismiss_entities=("session",)),
        name='ds_t1w_fsparc', run_without_submitting=True)

    workflow.connect([
        (inputnode, lta2itk_fwd, [('t1w2fsnative_xfm', 'in_xfms')]),
        (inputnode, lta2itk_inv, [('fsnative2t1w_xfm', 'in_xfms')]),
        (t1w_name, ds_t1w_fsnative, [('out', 'source_file')]),
        (lta2itk_fwd, ds_t1w_fsnative, [('out_xfm', 'in_file')]),
        (t1w_name, ds_fsnative_t1w, [('out', 'source_file')]),
        (lta2itk_inv, ds_fsnative_t1w, [('out_xfm', 'in_file')]),
        (inputnode, name_surfs, [('surfaces', 'in_file')]),
        (inputnode, ds_surfs, [('surfaces', 'in_file')]),
        (t1w_name, ds_surfs, [('out', 'source_file')]),
        (name_surfs, ds_surfs, [('hemi', 'hemi'),
                                ('suffix', 'suffix')]),
        (inputnode, ds_t1w_fsaseg, [('t1w_fs_aseg', 'in_file')]),
        (inputnode, ds_t1w_fsparc, [('t1w_fs_aparc', 'in_file')]),
        (t1w_name, ds_t1w_fsaseg, [('out', 'source_file')]),
        (t1w_name, ds_t1w_fsparc, [('out', 'source_file')]),
    ])
    return workflow


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


def _drop_cohort(in_template):
    return in_template.split(':')[0]


def _fmt_cohort(in_template):
    return in_template.replace(':', '_')


def _empty_report(in_file=None):
    from pathlib import Path
    from nipype.interfaces.base import isdefined
    if in_file is not None and isdefined(in_file):
        return in_file

    out_file = Path('tmp-report.html').absolute()
    out_file.write_text("""\
                <h4 class="elem-title">A previously computed T1w template was provided.</h4>
""")
    return str(out_file)

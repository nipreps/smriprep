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
"""Writing outputs."""

import typing as ty

from nipype.interfaces import utility as niu
from nipype.pipeline import engine as pe
from niworkflows.engine.workflows import LiterateWorkflow as Workflow
from niworkflows.interfaces.fixes import FixHeaderApplyTransforms as ApplyTransforms
from niworkflows.interfaces.nibabel import ApplyMask, GenerateSamplingReference
from niworkflows.interfaces.space import SpaceDataSource
from niworkflows.interfaces.utility import KeySelect

from ..interfaces import DerivativesDataSink
from ..interfaces.templateflow import TemplateFlowSelect, fetch_template_files

if ty.TYPE_CHECKING:
    from niworkflows.utils.spaces import SpatialReferences

BIDS_TISSUE_ORDER = ('GM', 'WM', 'CSF')


def init_anat_reports_wf(*, spaces, freesurfer, output_dir, sloppy=False, name='anat_reports_wf'):
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
    from niworkflows.interfaces.reportlets.masks import ROIsPlot
    from niworkflows.interfaces.reportlets.registration import (
        SimpleBeforeAfterRPT as SimpleBeforeAfter,
    )

    workflow = Workflow(name=name)

    inputfields = [
        'source_file',
        't1w_preproc',
        't1w_mask',
        't1w_dseg',
        'template',
        'anat2std_xfm',
        # May be missing
        't1w_conform_report',
        'subject_id',
        'subjects_dir',
    ]
    inputnode = pe.Node(niu.IdentityInterface(fields=inputfields), name='inputnode')

    seg_rpt = pe.Node(ROIsPlot(colors=['b', 'magenta'], levels=[1.5, 2.5]), name='seg_rpt')

    t1w_conform_check = pe.Node(
        niu.Function(function=_empty_report),
        name='t1w_conform_check',
        run_without_submitting=True,
    )

    ds_t1w_conform_report = pe.Node(
        DerivativesDataSink(base_directory=output_dir, desc='conform', datatype='figures'),
        name='ds_t1w_conform_report',
        run_without_submitting=True,
    )

    ds_t1w_dseg_mask_report = pe.Node(
        DerivativesDataSink(base_directory=output_dir, suffix='dseg', datatype='figures'),
        name='ds_t1w_dseg_mask_report',
        run_without_submitting=True,
    )

    # fmt:off
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
    # fmt:on

    if spaces._cached is not None and spaces.cached.references:
        template_iterator_wf = init_template_iterator_wf(spaces=spaces, sloppy=sloppy)
        t1w_std = pe.Node(
            ApplyTransforms(
                dimension=3,
                default_value=0,
                float=True,
                interpolation='LanczosWindowedSinc',
            ),
            name='t1w_std',
        )
        mask_std = pe.Node(
            ApplyTransforms(
                dimension=3,
                default_value=0,
                float=True,
                interpolation='MultiLabel',
            ),
            name='mask_std',
        )

        # Generate reportlets showing spatial normalization
        norm_msk = pe.Node(
            niu.Function(
                function=_rpt_masks,
                output_names=['before', 'after'],
                input_names=['mask_file', 'before', 'after', 'after_mask'],
            ),
            name='norm_msk',
        )
        norm_rpt = pe.Node(SimpleBeforeAfter(), name='norm_rpt', mem_gb=0.1)
        norm_rpt.inputs.after_label = 'Participant'  # after

        ds_std_t1w_report = pe.Node(
            DerivativesDataSink(base_directory=output_dir, suffix='T1w', datatype='figures'),
            name='ds_std_t1w_report',
            run_without_submitting=True,
        )

        # fmt:off
        workflow.connect([
            (inputnode, template_iterator_wf, [
                ('template', 'inputnode.template'),
                ('anat2std_xfm', 'inputnode.anat2std_xfm'),
            ]),
            (inputnode, t1w_std, [('t1w_preproc', 'input_image')]),
            (inputnode, mask_std, [('t1w_mask', 'input_image')]),
            (template_iterator_wf, t1w_std, [
                ('outputnode.anat2std_xfm', 'transforms'),
                ('outputnode.std_t1w', 'reference_image'),
            ]),
            (template_iterator_wf, mask_std, [
                ('outputnode.anat2std_xfm', 'transforms'),
                ('outputnode.std_t1w', 'reference_image'),
            ]),
            (template_iterator_wf, norm_rpt, [('outputnode.space', 'before_label')]),
            (t1w_std, norm_msk, [('output_image', 'after')]),
            (mask_std, norm_msk, [('output_image', 'after_mask')]),
            (template_iterator_wf, norm_msk, [
                ('outputnode.std_t1w', 'before'),
                ('outputnode.std_mask', 'mask_file'),
            ]),
            (norm_msk, norm_rpt, [
                ('before', 'before'),
                ('after', 'after'),
            ]),
            (inputnode, ds_std_t1w_report, [('source_file', 'source_file')]),
            (template_iterator_wf, ds_std_t1w_report, [('outputnode.space', 'space')]),
            (norm_rpt, ds_std_t1w_report, [('out_report', 'in_file')]),
        ])
        # fmt:on

    if freesurfer:
        from ..interfaces.reports import FSSurfaceReport

        recon_report = pe.Node(FSSurfaceReport(), name='recon_report')
        recon_report.interface._always_run = True

        ds_recon_report = pe.Node(
            DerivativesDataSink(base_directory=output_dir, desc='reconall', datatype='figures'),
            name='ds_recon_report',
            run_without_submitting=True,
        )
        # fmt:off
        workflow.connect([
            (inputnode, recon_report, [('subjects_dir', 'subjects_dir'),
                                       ('subject_id', 'subject_id')]),
            (recon_report, ds_recon_report, [('out_report', 'in_file')]),
            (inputnode, ds_recon_report, [('source_file', 'source_file')])
        ])
        # fmt:on

    return workflow


def init_ds_template_wf(
    *,
    num_t1w,
    output_dir,
    name='ds_template_wf',
):
    """
    Save the subject-specific template

    Parameters
    ----------
    num_t1w : :obj:`int`
        Number of T1w images
    output_dir : :obj:`str`
        Directory in which to save derivatives
    name : :obj:`str`
        Workflow name (default: ds_template_wf)

    Inputs
    ------
    source_files
        List of input T1w images
    t1w_ref_xfms
        List of affine transforms to realign input T1w images
    t1w_preproc
        The T1w reference map, which is calculated as the average of bias-corrected
        and preprocessed T1w images, defining the anatomical space.

    Outputs
    -------
    t1w_preproc
        The location in the output directory of the preprocessed T1w image

    """
    workflow = Workflow(name=name)

    inputnode = pe.Node(
        niu.IdentityInterface(
            fields=[
                'source_files',
                't1w_ref_xfms',
                't1w_preproc',
            ]
        ),
        name='inputnode',
    )
    outputnode = pe.Node(niu.IdentityInterface(fields=['t1w_preproc']), name='outputnode')

    ds_t1w_preproc = pe.Node(
        DerivativesDataSink(base_directory=output_dir, desc='preproc', compress=True),
        name='ds_t1w_preproc',
        run_without_submitting=True,
    )
    ds_t1w_preproc.inputs.SkullStripped = False

    # fmt:off
    workflow.connect([
        (inputnode, ds_t1w_preproc, [('t1w_preproc', 'in_file'),
                                     ('source_files', 'source_file')]),
        (ds_t1w_preproc, outputnode, [('out_file', 't1w_preproc')]),
    ])
    # fmt:on

    if num_t1w > 1:
        # Please note the dictionary unpacking to provide the from argument.
        # It is necessary because from is a protected keyword (not allowed as argument name).
        ds_t1w_ref_xfms = pe.MapNode(
            DerivativesDataSink(
                base_directory=output_dir,
                to='T1w',
                mode='image',
                suffix='xfm',
                extension='txt',
                **{'from': 'orig'},
            ),
            iterfield=['source_file', 'in_file'],
            name='ds_t1w_ref_xfms',
            run_without_submitting=True,
        )
        # fmt:off
        workflow.connect([
            (inputnode, ds_t1w_ref_xfms, [('source_files', 'source_file'),
                                          ('t1w_ref_xfms', 'in_file')]),
        ])
        # fmt:on

    return workflow


def init_ds_mask_wf(
    *,
    bids_root: str,
    output_dir: str,
    mask_type: str,
    name='ds_mask_wf',
):
    """
    Save the subject brain mask

    Parameters
    ----------
    bids_root : :obj:`str`
        Root path of BIDS dataset
    output_dir : :obj:`str`
        Directory in which to save derivatives
    name : :obj:`str`
        Workflow name (default: ds_mask_wf)

    Inputs
    ------
    source_files
        List of input T1w images
    mask_file
        Mask to save

    Outputs
    -------
    mask_file
        The location in the output directory of the mask

    """
    workflow = Workflow(name=name)

    inputnode = pe.Node(
        niu.IdentityInterface(fields=['source_files', 'mask_file']),
        name='inputnode',
    )
    outputnode = pe.Node(niu.IdentityInterface(fields=['mask_file']), name='outputnode')

    raw_sources = pe.Node(niu.Function(function=_bids_relative), name='raw_sources')
    raw_sources.inputs.bids_root = bids_root

    ds_mask = pe.Node(
        DerivativesDataSink(
            base_directory=output_dir,
            desc=mask_type,
            suffix='mask',
            compress=True,
        ),
        name='ds_t1w_mask',
        run_without_submitting=True,
    )
    if mask_type == 'brain':
        ds_mask.inputs.Type = 'Brain'
    else:
        ds_mask.inputs.Type = 'ROI'

    # fmt:off
    workflow.connect([
        (inputnode, raw_sources, [('source_files', 'in_files')]),
        (inputnode, ds_mask, [('mask_file', 'in_file'),
                              ('source_files', 'source_file')]),
        (raw_sources, ds_mask, [('out', 'RawSources')]),
        (ds_mask, outputnode, [('out_file', 'mask_file')]),
    ])
    # fmt:on

    return workflow


def init_ds_dseg_wf(*, output_dir, name='ds_dseg_wf'):
    """
    Save discrete segmentations

    Parameters
    ----------
    output_dir : :obj:`str`
        Directory in which to save derivatives
    name : :obj:`str`
        Workflow name (default: ds_dseg_wf)

    Inputs
    ------
    source_files
        List of input T1w images
    t1w_dseg
        Segmentation in T1w space

    Outputs
    -------
    t1w_dseg
        The location in the output directory of the discrete segmentation

    """
    workflow = Workflow(name=name)

    inputnode = pe.Node(
        niu.IdentityInterface(fields=['source_files', 't1w_dseg']),
        name='inputnode',
    )
    outputnode = pe.Node(niu.IdentityInterface(fields=['t1w_dseg']), name='outputnode')

    ds_t1w_dseg = pe.Node(
        DerivativesDataSink(
            base_directory=output_dir,
            suffix='dseg',
            compress=True,
            dismiss_entities=['desc'],
        ),
        name='ds_t1w_dseg',
        run_without_submitting=True,
    )

    # fmt:off
    workflow.connect([
        (inputnode, ds_t1w_dseg, [('t1w_dseg', 'in_file'),
                                  ('source_files', 'source_file')]),
        (ds_t1w_dseg, outputnode, [('out_file', 't1w_dseg')]),
    ])
    # fmt:on

    return workflow


def init_ds_tpms_wf(*, output_dir, name='ds_tpms_wf', tpm_labels=BIDS_TISSUE_ORDER):
    """
    Save tissue probability maps

    Parameters
    ----------
    output_dir : :obj:`str`
        Directory in which to save derivatives
    name : :obj:`str`
        Workflow name (default: anat_derivatives_wf)
    tpm_labels : :obj:`tuple`
        Tissue probability maps in order

    Inputs
    ------
    source_files
        List of input T1w images
    t1w_tpms
        Tissue probability maps in T1w space

    Outputs
    -------
    t1w_tpms
        The location in the output directory of the tissue probability maps

    """
    workflow = Workflow(name=name)

    inputnode = pe.Node(
        niu.IdentityInterface(fields=['source_files', 't1w_tpms']),
        name='inputnode',
    )
    outputnode = pe.Node(niu.IdentityInterface(fields=['t1w_tpms']), name='outputnode')

    ds_t1w_tpms = pe.Node(
        DerivativesDataSink(
            base_directory=output_dir,
            suffix='probseg',
            compress=True,
            dismiss_entities=['desc'],
        ),
        name='ds_t1w_tpms',
        run_without_submitting=True,
    )
    ds_t1w_tpms.inputs.label = tpm_labels

    # fmt:off
    workflow.connect([
        (inputnode, ds_t1w_tpms, [('t1w_tpms', 'in_file'),
                                  ('source_files', 'source_file')]),
        (ds_t1w_tpms, outputnode, [('out_file', 't1w_tpms')]),
    ])
    # fmt:on

    return workflow


def init_ds_template_registration_wf(
    *,
    output_dir,
    name='ds_template_registration_wf',
):
    """
    Save template registration transforms

    Parameters
    ----------
    output_dir : :obj:`str`
        Directory in which to save derivatives
    name : :obj:`str`
        Workflow name (default: anat_derivatives_wf)

    Inputs
    ------
    template
        Template space and specifications
    source_files
        List of input T1w images
    anat2std_xfm
        Nonlinear spatial transform to resample imaging data given in anatomical space
        into standard space.
    std2anat_xfm
        Inverse transform of ``anat2std_xfm``

    """
    workflow = Workflow(name=name)

    inputnode = pe.Node(
        niu.IdentityInterface(fields=['template', 'source_files', 'anat2std_xfm', 'std2anat_xfm']),
        name='inputnode',
    )
    outputnode = pe.Node(
        niu.IdentityInterface(fields=['anat2std_xfm', 'std2anat_xfm']),
        name='outputnode',
    )

    ds_std2t1w_xfm = pe.MapNode(
        DerivativesDataSink(
            base_directory=output_dir,
            to='T1w',
            mode='image',
            suffix='xfm',
            dismiss_entities=['desc'],
        ),
        iterfield=('in_file', 'from'),
        name='ds_std2t1w_xfm',
        run_without_submitting=True,
    )

    ds_t1w2std_xfm = pe.MapNode(
        DerivativesDataSink(
            base_directory=output_dir,
            mode='image',
            suffix='xfm',
            dismiss_entities=['desc'],
            **{'from': 'T1w'},
        ),
        iterfield=('in_file', 'to'),
        name='ds_t1w2std_xfm',
        run_without_submitting=True,
    )

    # fmt:off
    workflow.connect([
        (inputnode, ds_t1w2std_xfm, [
            ('anat2std_xfm', 'in_file'),
            (('template', _combine_cohort), 'to'),
            ('source_files', 'source_file')]),
        (inputnode, ds_std2t1w_xfm, [
            ('std2anat_xfm', 'in_file'),
            (('template', _combine_cohort), 'from'),
            ('source_files', 'source_file')]),
        (ds_t1w2std_xfm, outputnode, [('out_file', 'anat2std_xfm')]),
        (ds_std2t1w_xfm, outputnode, [('out_file', 'std2anat_xfm')]),
    ])
    # fmt:on

    return workflow


def init_ds_fs_registration_wf(
    *,
    output_dir,
    name='ds_fs_registration_wf',
):
    """
    Save rigid registration between subject anatomical template and FreeSurfer T1.mgz

    Parameters
    ----------
    output_dir : :obj:`str`
        Directory in which to save derivatives
    name : :obj:`str`
        Workflow name (default: ds_fs_registration_wf)

    Inputs
    ------
    source_files
        List of input T1w images
    fsnative2t1w_xfm
        LTA-style affine matrix translating from FreeSurfer-conformed
        subject space to T1w

    Outputs
    -------
    t1w2fsnative_xfm
        LTA-style affine matrix translating from T1w to
        FreeSurfer-conformed subject space
    fsnative2t1w_xfm
        LTA-style affine matrix translating from FreeSurfer-conformed
        subject space to T1w

    """
    workflow = Workflow(name=name)

    inputnode = pe.Node(
        niu.IdentityInterface(fields=['source_files', 'fsnative2t1w_xfm']),
        name='inputnode',
    )
    outputnode = pe.Node(
        niu.IdentityInterface(fields=['fsnative2t1w_xfm', 't1w2fsnative_xfm']),
        name='outputnode',
    )

    from niworkflows.interfaces.nitransforms import ConcatenateXFMs

    # FS native space transforms
    lta2itk = pe.Node(ConcatenateXFMs(inverse=True), name='lta2itk', run_without_submitting=True)
    ds_t1w_fsnative = pe.Node(
        DerivativesDataSink(
            base_directory=output_dir,
            mode='image',
            to='fsnative',
            suffix='xfm',
            extension='txt',
            **{'from': 'T1w'},
        ),
        name='ds_t1w_fsnative',
        run_without_submitting=True,
    )
    ds_fsnative_t1w = pe.Node(
        DerivativesDataSink(
            base_directory=output_dir,
            mode='image',
            to='T1w',
            suffix='xfm',
            extension='txt',
            **{'from': 'fsnative'},
        ),
        name='ds_fsnative_t1w',
        run_without_submitting=True,
    )

    # fmt:off
    workflow.connect([
        (inputnode, lta2itk, [('fsnative2t1w_xfm', 'in_xfms')]),
        (inputnode, ds_t1w_fsnative, [('source_files', 'source_file')]),
        (lta2itk, ds_t1w_fsnative, [('out_inv', 'in_file')]),
        (inputnode, ds_fsnative_t1w, [('source_files', 'source_file')]),
        (lta2itk, ds_fsnative_t1w, [('out_xfm', 'in_file')]),
        (ds_fsnative_t1w, outputnode, [('out_file', 'fsnative2t1w_xfm')]),
        (ds_t1w_fsnative, outputnode, [('out_file', 't1w2fsnative_xfm')]),
    ])
    # fmt:on
    return workflow


def init_ds_surfaces_wf(
    *,
    bids_root: str,
    output_dir: str,
    surfaces: list[str],
    name='ds_surfaces_wf',
) -> Workflow:
    """
    Save GIFTI surfaces

    Parameters
    ----------
    bids_root : :class:`str`
        Root path of BIDS dataset
    output_dir : :class:`str`
        Directory in which to save derivatives
    surfaces : :class:`str`
        List of surfaces to generate DataSinks for
    name : :class:`str`
        Workflow name (default: ds_surfaces_wf)

    Inputs
    ------
    source_files
        List of input T1w images
    ``<surface>``
        Left and right GIFTIs for each surface passed to ``surfaces``

    Outputs
    -------
    ``<surface>``
        Left and right GIFTIs in ``output_dir`` for each surface passed to ``surfaces``

    """
    workflow = Workflow(name=name)

    inputnode = pe.Node(
        niu.IdentityInterface(fields=['source_files'] + surfaces),
        name='inputnode',
    )
    outputnode = pe.Node(niu.IdentityInterface(fields=surfaces), name='outputnode')

    for surf in surfaces:
        ds_surf = pe.MapNode(
            DerivativesDataSink(
                base_directory=output_dir,
                hemi=['L', 'R'],
                suffix=surf.split('_')[0],  # Split for sphere_reg and sphere_reg_fsLR
                extension='.surf.gii',
            ),
            iterfield=('in_file', 'hemi'),
            name=f'ds_{surf}',
            run_without_submitting=True,
        )
        if surf.startswith('sphere_reg'):
            ds_surf.inputs.space, ds_surf.inputs.desc = 'fsaverage', 'reg'  # Default
            if surf == 'sphere_reg_fsLR':
                ds_surf.inputs.space = 'fsLR'
            elif surf == 'sphere_reg_msm':
                ds_surf.inputs.space, ds_surf.inputs.desc = 'fsLR', 'msmsulc'

        # fmt:off
        workflow.connect([
            (inputnode, ds_surf, [(surf, 'in_file'), ('source_files', 'source_file')]),
            (ds_surf, outputnode, [('out_file', surf)]),
        ])
        # fmt:on

    return workflow


def init_ds_surface_metrics_wf(
    *,
    bids_root: str,
    output_dir: str,
    metrics: list[str],
    name='ds_surface_metrics_wf',
) -> Workflow:
    """
    Save GIFTI surface metrics

    Parameters
    ----------
    bids_root : :class:`str`
        Root path of BIDS dataset
    output_dir : :class:`str`
        Directory in which to save derivatives
    metrics : :class:`str`
        List of metrics to generate DataSinks for
    name : :class:`str`
        Workflow name (default: ds_surface_metrics_wf)

    Inputs
    ------
    source_files
        List of input T1w images
    ``<metric>``
        Left and right GIFTIs for each metric passed to ``metrics``

    Outputs
    -------
    ``<metric>``
        Left and right GIFTIs in ``output_dir`` for each metric passed to ``metrics``

    """
    workflow = Workflow(name=name)

    inputnode = pe.Node(
        niu.IdentityInterface(fields=['source_files'] + metrics),
        name='inputnode',
    )
    outputnode = pe.Node(niu.IdentityInterface(fields=metrics), name='outputnode')

    for metric in metrics:
        ds_surf = pe.MapNode(
            DerivativesDataSink(
                base_directory=output_dir,
                hemi=['L', 'R'],
                suffix=metric,
                extension='.shape.gii',
            ),
            iterfield=('in_file', 'hemi'),
            name=f'ds_{metric}',
            run_without_submitting=True,
        )

        # fmt:off
        workflow.connect([
            (inputnode, ds_surf, [(metric, 'in_file'), ('source_files', 'source_file')]),
            (ds_surf, outputnode, [('out_file', metric)]),
        ])
        # fmt:on

    return workflow


def init_ds_grayord_metrics_wf(
    *,
    bids_root: str,
    output_dir: str,
    metrics: list[str],
    cifti_output: ty.Literal['91k', '170k'],
    name='ds_grayord_metrics_wf',
) -> Workflow:
    """
    Save CIFTI-2 surface metrics

    Parameters
    ----------
    bids_root : :class:`str`
        Root path of BIDS dataset
    output_dir : :class:`str`
        Directory in which to save derivatives
    metrics : :class:`str`
        List of metrics to generate DataSinks for
    cifti_output : :class:`str`
        Density of CIFTI-2 files to save
    name : :class:`str`
        Workflow name (default: ds_surface_metrics_wf)

    Inputs
    ------
    source_files
        List of input T1w images
    ``<metric>``
        CIFTI-2 scalar file for each metric passed to ``metrics``
    ``<metric>_metadata``
        JSON file containing metadata for each metric passed to ``metrics``

    Outputs
    -------
    ``<metric>``
        CIFTI-2 scalar file in ``output_dir`` for each metric passed to ``metrics``

    """
    workflow = Workflow(name=name)

    inputnode = pe.Node(
        niu.IdentityInterface(
            fields=['source_files'] + metrics + [f'{m}_metadata' for m in metrics]
        ),
        name='inputnode',
    )
    outputnode = pe.Node(niu.IdentityInterface(fields=metrics), name='outputnode')

    for metric in metrics:
        ds_metric = pe.Node(
            DerivativesDataSink(
                base_directory=output_dir,
                space='fsLR',
                density=cifti_output,
                suffix=metric,
                compress=False,
                extension='.dscalar.nii',
            ),
            name=f'ds_{metric}',
            run_without_submitting=True,
        )

        workflow.connect([
            (inputnode, ds_metric, [
                ('source_files', 'source_file'),
                (metric, 'in_file'),
                ((f'{metric}_metadata', _read_json), 'meta_dict'),
            ]),
            (ds_metric, outputnode, [('out_file', metric)]),
        ])  # fmt:skip

    return workflow


def init_ds_anat_volumes_wf(
    *,
    bids_root: str,
    output_dir: str,
    name='ds_anat_volumes_wf',
    tpm_labels=BIDS_TISSUE_ORDER,
) -> pe.Workflow:
    workflow = pe.Workflow(name=name)
    inputnode = pe.Node(
        niu.IdentityInterface(
            fields=[
                # Original T1w image
                'source_files',
                # T1w-space images
                't1w_preproc',
                't1w_mask',
                't1w_dseg',
                't1w_tpms',
                # Template
                'ref_file',
                'anat2std_xfm',
                # Entities
                'space',
                'cohort',
                'resolution',
            ]
        ),
        name='inputnode',
    )

    raw_sources = pe.Node(niu.Function(function=_bids_relative), name='raw_sources')
    raw_sources.inputs.bids_root = bids_root

    gen_ref = pe.Node(GenerateSamplingReference(), name='gen_ref', mem_gb=0.01)

    # Mask T1w preproc images
    mask_t1w = pe.Node(ApplyMask(), name='mask_t1w')

    # Resample T1w-space inputs
    anat2std_t1w = pe.Node(
        ApplyTransforms(
            dimension=3,
            default_value=0,
            float=True,
            interpolation='LanczosWindowedSinc',
        ),
        name='anat2std_t1w',
    )

    anat2std_mask = pe.Node(ApplyTransforms(interpolation='MultiLabel'), name='anat2std_mask')
    anat2std_dseg = pe.Node(ApplyTransforms(interpolation='MultiLabel'), name='anat2std_dseg')
    anat2std_tpms = pe.MapNode(
        ApplyTransforms(dimension=3, default_value=0, float=True, interpolation='Gaussian'),
        iterfield=['input_image'],
        name='anat2std_tpms',
    )

    ds_std_t1w = pe.Node(
        DerivativesDataSink(
            base_directory=output_dir,
            desc='preproc',
            compress=True,
        ),
        name='ds_std_t1w',
        run_without_submitting=True,
    )
    ds_std_t1w.inputs.SkullStripped = True

    ds_std_mask = pe.Node(
        DerivativesDataSink(base_directory=output_dir, desc='brain', suffix='mask', compress=True),
        name='ds_std_mask',
        run_without_submitting=True,
    )
    ds_std_mask.inputs.Type = 'Brain'

    ds_std_dseg = pe.Node(
        DerivativesDataSink(base_directory=output_dir, suffix='dseg', compress=True),
        name='ds_std_dseg',
        run_without_submitting=True,
    )

    ds_std_tpms = pe.Node(
        DerivativesDataSink(base_directory=output_dir, suffix='probseg', compress=True),
        name='ds_std_tpms',
        run_without_submitting=True,
    )

    # CRITICAL: the sequence of labels here (CSF-GM-WM) is that of the output of FSL-FAST
    #           (intensity mean, per tissue). This order HAS to be matched also by the ``tpms``
    #           output in the data/io_spec.json file.
    ds_std_tpms.inputs.label = tpm_labels

    workflow.connect([
        (inputnode, gen_ref, [
            ('ref_file', 'fixed_image'),
            (('resolution', _is_native), 'keep_native'),
        ]),
        (inputnode, mask_t1w, [
            ('t1w_preproc', 'in_file'),
            ('t1w_mask', 'in_mask'),
        ]),
        (mask_t1w, anat2std_t1w, [('out_file', 'input_image')]),
        (inputnode, anat2std_mask, [('t1w_mask', 'input_image')]),
        (inputnode, anat2std_dseg, [('t1w_dseg', 'input_image')]),
        (inputnode, anat2std_tpms, [('t1w_tpms', 'input_image')]),
        (inputnode, gen_ref, [('t1w_preproc', 'moving_image')]),
        (anat2std_t1w, ds_std_t1w, [('output_image', 'in_file')]),
        (anat2std_mask, ds_std_mask, [('output_image', 'in_file')]),
        (anat2std_dseg, ds_std_dseg, [('output_image', 'in_file')]),
        (anat2std_tpms, ds_std_tpms, [('output_image', 'in_file')]),
    ])  # fmt:skip

    workflow.connect(
        # Connect apply transforms nodes
        [
            (gen_ref, n, [('out_file', 'reference_image')])
            for n in (anat2std_t1w, anat2std_mask, anat2std_dseg, anat2std_tpms)
        ]
        + [
            (inputnode, n, [('anat2std_xfm', 'transforms')])
            for n in (anat2std_t1w, anat2std_mask, anat2std_dseg, anat2std_tpms)
        ]
        + [
            (inputnode, n, [
                ('source_files', 'source_file'),
                ('space', 'space'),
                ('cohort', 'cohort'),
                ('resolution', 'resolution'),
            ])
            for n in (ds_std_t1w, ds_std_mask, ds_std_dseg, ds_std_tpms)
        ]
    )  # fmt:skip

    return workflow


def init_anat_second_derivatives_wf(
    *,
    bids_root: str,
    output_dir: str,
    cifti_output: ty.Literal['91k', '170k', False],
    name='anat_second_derivatives_wf',
    tpm_labels=BIDS_TISSUE_ORDER,
):
    """
    Set up a battery of datasinks to store derivatives in the right location.

    Parameters
    ----------
    bids_root : :obj:`str`
        Root path of BIDS dataset
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
    surfaces
        GIFTI surfaces (gray/white boundary, midthickness, pial, inflated)
    morphometrics
        GIFTIs of cortical thickness, curvature, and sulcal depth
    t1w_fs_aseg
        FreeSurfer's aseg segmentation, in native T1w space
    t1w_fs_aparc
        FreeSurfer's aparc+aseg segmentation, in native T1w space
    cifti_morph
        Morphometric CIFTI-2 dscalar files
    cifti_metadata
        JSON files containing metadata dictionaries

    """
    workflow = Workflow(name=name)

    inputnode = pe.Node(
        niu.IdentityInterface(
            fields=[
                'template',
                'source_files',
                't1w_fs_aseg',
                't1w_fs_aparc',
            ]
        ),
        name='inputnode',
    )

    raw_sources = pe.Node(niu.Function(function=_bids_relative), name='raw_sources')
    raw_sources.inputs.bids_root = bids_root

    # Parcellations
    ds_t1w_fsaseg = pe.Node(
        DerivativesDataSink(base_directory=output_dir, desc='aseg', suffix='dseg', compress=True),
        name='ds_t1w_fsaseg',
        run_without_submitting=True,
    )
    ds_t1w_fsparc = pe.Node(
        DerivativesDataSink(
            base_directory=output_dir, desc='aparcaseg', suffix='dseg', compress=True
        ),
        name='ds_t1w_fsparc',
        run_without_submitting=True,
    )

    # fmt:off
    workflow.connect([
        (inputnode, ds_t1w_fsaseg, [('t1w_fs_aseg', 'in_file'),
                                    ('source_files', 'source_file')]),
        (inputnode, ds_t1w_fsparc, [('t1w_fs_aparc', 'in_file'),
                                    ('source_files', 'source_file')]),
    ])
    # fmt:on

    return workflow


def init_template_iterator_wf(
    *, spaces: 'SpatialReferences', sloppy: bool = False, name='template_iterator_wf'
):
    """Prepare the necessary components to resample an image to a template space

    This produces a workflow with an unjoined iterable named "spacesource".

    It takes as input a collated list of template specifiers and transforms to that
    space.

    The fields in `outputnode` can be used as if they come from a single template.
    """
    for template in spaces.get_spaces(nonstandard=False, dim=(3,)):
        fetch_template_files(template, specs=None, sloppy=sloppy)

    workflow = pe.Workflow(name=name)

    inputnode = pe.Node(
        niu.IdentityInterface(fields=['template', 'anat2std_xfm']),
        name='inputnode',
    )
    outputnode = pe.Node(
        niu.IdentityInterface(
            fields=[
                'space',
                'resolution',
                'cohort',
                'anat2std_xfm',
                'std_t1w',
                'std_mask',
            ],
        ),
        name='outputnode',
    )

    spacesource = pe.Node(SpaceDataSource(), name='spacesource', run_without_submitting=True)
    spacesource.iterables = (
        'in_tuple',
        [(s.fullname, s.spec) for s in spaces.cached.get_standard(dim=(3,))],
    )

    gen_tplid = pe.Node(
        niu.Function(function=_fmt_cohort),
        name='gen_tplid',
        run_without_submitting=True,
    )

    select_xfm = pe.Node(
        KeySelect(fields=['anat2std_xfm']),
        name='select_xfm',
        run_without_submitting=True,
    )
    select_tpl = pe.Node(TemplateFlowSelect(), name='select_tpl', run_without_submitting=True)

    # fmt:off
    workflow.connect([
        (inputnode, select_xfm, [
            ('anat2std_xfm', 'anat2std_xfm'),
            ('template', 'keys'),
        ]),
        (spacesource, gen_tplid, [
            ('space', 'template'),
            ('cohort', 'cohort'),
        ]),
        (gen_tplid, select_xfm, [('out', 'key')]),
        (spacesource, select_tpl, [
            ('space', 'template'),
            ('cohort', 'cohort'),
            (('resolution', _no_native, sloppy), 'resolution'),
        ]),
        (spacesource, outputnode, [
            ('space', 'space'),
            ('resolution', 'resolution'),
            ('cohort', 'cohort'),
        ]),
        (select_xfm, outputnode, [
            ('anat2std_xfm', 'anat2std_xfm'),
        ]),
        (select_tpl, outputnode, [
            ('t1w_file', 'std_t1w'),
            ('brain_mask', 'std_mask'),
        ]),
    ])
    # fmt:on

    return workflow


def _bids_relative(in_files, bids_root):
    from pathlib import Path

    if not isinstance(in_files, list | tuple):
        in_files = [in_files]
    ret = []
    for file in in_files:
        try:
            ret.append(str(Path(file).relative_to(bids_root)))
        except ValueError:
            ret.append(file)
    return in_files


def _rpt_masks(mask_file, before, after, after_mask=None):
    from os.path import abspath

    import nibabel as nb

    msk = nb.load(mask_file).get_fdata() > 0
    bnii = nb.load(before)
    nb.Nifti1Image(bnii.get_fdata() * msk, bnii.affine, bnii.header).to_filename('before.nii.gz')
    if after_mask is not None:
        msk = nb.load(after_mask).get_fdata() > 0

    anii = nb.load(after)
    nb.Nifti1Image(anii.get_fdata() * msk, anii.affine, anii.header).to_filename('after.nii.gz')
    return abspath('before.nii.gz'), abspath('after.nii.gz')


def _drop_cohort(in_template):
    if isinstance(in_template, str):
        return in_template.split(':')[0]
    return [_drop_cohort(v) for v in in_template]


def _pick_cohort(in_template):
    if isinstance(in_template, str):
        if 'cohort-' not in in_template:
            from nipype.interfaces.base import Undefined

            return Undefined
        return in_template.split('cohort-')[-1].split(':')[0]
    return [_pick_cohort(v) for v in in_template]


def _empty_report(in_file=None):
    from pathlib import Path

    from nipype.interfaces.base import isdefined

    if in_file is not None and isdefined(in_file):
        return in_file

    out_file = Path('tmp-report.html').absolute()
    out_file.write_text(
        """\
                <h4 class="elem-title">A previously computed T1w template was provided.</h4>
"""
    )
    return str(out_file)


def _is_native(value):
    return value == 'native'


def _no_native(value, sloppy=False):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 2 if sloppy else 1


def _drop_path(in_path):
    from pathlib import Path

    from templateflow.conf import TF_HOME

    return str(Path(in_path).relative_to(TF_HOME))


def _fmt_cohort(template, cohort=None):
    from nipype.interfaces.base import isdefined

    if cohort and isdefined(cohort):
        return f'{template}:cohort-{cohort}'
    return template


def _combine_cohort(in_template):
    if isinstance(in_template, str):
        template = in_template.split(':')[0]
        if 'cohort-' not in in_template:
            return template
        return f"{template}+{in_template.split('cohort-')[-1].split(':')[0]}"
    return [_combine_cohort(v) for v in in_template]


def _read_json(in_file):
    from json import loads
    from pathlib import Path

    return loads(Path(in_file).read_text())

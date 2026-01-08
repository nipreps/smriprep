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
from niworkflows.engine import Workflow, tag
from niworkflows.interfaces.fixes import FixHeaderApplyTransforms as ApplyTransforms
from niworkflows.interfaces.nibabel import ApplyMask, GenerateSamplingReference
from niworkflows.interfaces.space import SpaceDataSource
from niworkflows.interfaces.utility import KeySelect

from ..interfaces import DerivativesDataSink
from ..interfaces.templateflow import TemplateFlowSelect, fetch_template_files

if ty.TYPE_CHECKING:
    from niworkflows.utils.spaces import SpatialReferences

BIDS_TISSUE_ORDER = ('GM', 'WM', 'CSF')


@tag('anat.reports')
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
    num_anat: int,
    output_dir: str,
    image_type: ty.Literal['T1w', 'T2w'],
    name: str = 'ds_template_wf',
):
    """
    Save the subject-specific template

    Parameters
    ----------
    num_anat : :obj:`int`
        Number of anatomical images
    output_dir : :obj:`str`
        Directory in which to save derivatives
    image_type
        MR image type (T1w, T2w, etc.)
    name : :obj:`str`
        Workflow name (default: ds_template_wf)

    Inputs
    ------
    source_files
        List of input anatomical images
    anat_ref_xfms
        List of affine transforms to realign input anatomical images
    anat_preproc
        The anatomical reference map, which is calculated as the average of bias-corrected
        and preprocessed anatomical images, defining the anatomical space.

    Outputs
    -------
    anat_preproc
        The location in the output directory of the preprocessed anatomical image

    """
    workflow = Workflow(name=name)

    inputnode = pe.Node(
        niu.IdentityInterface(
            fields=[
                'source_files',
                'anat_ref_xfms',
                'anat_preproc',
            ]
        ),
        name='inputnode',
    )
    outputnode = pe.Node(niu.IdentityInterface(fields=['anat_preproc']), name='outputnode')

    ds_anat_preproc = pe.Node(
        DerivativesDataSink(base_directory=output_dir, desc='preproc', compress=True),
        name='ds_anat_preproc',
        run_without_submitting=True,
    )
    ds_anat_preproc.inputs.SkullStripped = False

    # fmt:off
    workflow.connect([
        (inputnode, ds_anat_preproc, [('anat_preproc', 'in_file'),
                                     ('source_files', 'source_file')]),
        (ds_anat_preproc, outputnode, [('out_file', 'anat_preproc')]),
    ])
    # fmt:on

    if num_anat > 1:
        # Please note the dictionary unpacking to provide the from argument.
        # It is necessary because from is a protected keyword (not allowed as argument name).
        ds_anat_ref_xfms = pe.MapNode(
            DerivativesDataSink(
                base_directory=output_dir,
                to=image_type,
                mode='image',
                suffix='xfm',
                extension='txt',
                **{'from': 'orig'},
            ),
            iterfield=['source_file', 'in_file'],
            name='ds_anat_ref_xfms',
            run_without_submitting=True,
        )
        # fmt:off
        workflow.connect([
            (inputnode, ds_anat_ref_xfms, [('source_files', 'source_file'),
                                           ('anat_ref_xfms', 'in_file')]),
        ])
        # fmt:on

    return workflow


def init_ds_mask_wf(
    *,
    bids_root: str,
    output_dir: str,
    mask_type: ty.Literal['brain', 'roi', 'ribbon'],
    extra_entities: dict | None = None,
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
    extra_entities : :obj:`dict` or None
        Additional entities to add to filename
    name : :obj:`str`
        Workflow name (default: ds_mask_wf)

    Inputs
    ------
    source_files
        List of input anat images
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

    extra_entities = extra_entities or {}

    ds_mask = pe.Node(
        DerivativesDataSink(
            base_directory=output_dir,
            desc=mask_type,
            suffix='mask',
            compress=True,
            **extra_entities,
        ),
        name='ds_anat_mask',
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


def init_ds_dseg_wf(
    *,
    output_dir: str,
    extra_entities: dict | None = None,
    name: str = 'ds_dseg_wf',
):
    """
    Save discrete segmentations

    Parameters
    ----------
    output_dir : :obj:`str`
        Directory in which to save derivatives
    extra_entities : :obj:`dict` or None
        Additional entities to add to filename
    name : :obj:`str`
        Workflow name (default: ds_dseg_wf)

    Inputs
    ------
    source_files
        List of input anatomical images
    anat_dseg
        Segmentation in anatomical space

    Outputs
    -------
    anat_dseg
        The location in the output directory of the discrete segmentation

    """
    workflow = Workflow(name=name)

    inputnode = pe.Node(
        niu.IdentityInterface(fields=['source_files', 'anat_dseg']),
        name='inputnode',
    )
    outputnode = pe.Node(niu.IdentityInterface(fields=['anat_dseg']), name='outputnode')

    extra_entities = extra_entities or {}

    ds_anat_dseg = pe.Node(
        DerivativesDataSink(
            base_directory=output_dir,
            suffix='dseg',
            compress=True,
            dismiss_entities=['desc'],
            **extra_entities,
        ),
        name='ds_anat_dseg',
        run_without_submitting=True,
    )

    # fmt:off
    workflow.connect([
        (inputnode, ds_anat_dseg, [('anat_dseg', 'in_file'),
                                  ('source_files', 'source_file')]),
        (ds_anat_dseg, outputnode, [('out_file', 'anat_dseg')]),
    ])
    # fmt:on

    return workflow


def init_ds_tpms_wf(
    *,
    output_dir: str,
    extra_entities: dict | None = None,
    name: str = 'ds_tpms_wf',
    tpm_labels: tuple = BIDS_TISSUE_ORDER,
):
    """
    Save tissue probability maps

    Parameters
    ----------
    output_dir : :obj:`str`
        Directory in which to save derivatives
    extra_entities : :obj:`dict` or None
        Additional entities to add to filename
    name : :obj:`str`
        Workflow name (default: anat_derivatives_wf)
    tpm_labels : :obj:`tuple`
        Tissue probability maps in order

    Inputs
    ------
    source_files
        List of input anatomical images
    anat_tpms
        Tissue probability maps in anatomical space

    Outputs
    -------
    anat_tpms
        The location in the output directory of the tissue probability maps

    """
    workflow = Workflow(name=name)

    inputnode = pe.Node(
        niu.IdentityInterface(fields=['source_files', 'anat_tpms']),
        name='inputnode',
    )
    outputnode = pe.Node(niu.IdentityInterface(fields=['anat_tpms']), name='outputnode')

    extra_entities = extra_entities or {}

    ds_anat_tpms = pe.Node(
        DerivativesDataSink(
            base_directory=output_dir,
            suffix='probseg',
            compress=True,
            dismiss_entities=['desc'],
            **extra_entities,
        ),
        name='ds_anat_tpms',
        run_without_submitting=True,
    )
    ds_anat_tpms.inputs.label = tpm_labels

    # fmt:off
    workflow.connect([
        (inputnode, ds_anat_tpms, [('anat_tpms', 'in_file'),
                                  ('source_files', 'source_file')]),
        (ds_anat_tpms, outputnode, [('out_file', 'anat_tpms')]),
    ])
    # fmt:on

    return workflow


def init_ds_template_registration_wf(
    *,
    output_dir: str,
    image_type: ty.Literal['T1w', 'T2w'],
    name: str = 'ds_template_registration_wf',
):
    """
    Save template registration transforms

    Parameters
    ----------
    output_dir : :obj:`str`
        Directory in which to save derivatives
    image_type : :obj:`str`
        Anatomical image type (T1w, T2w, etc)
    name : :obj:`str`
        Workflow name (default: anat_derivatives_wf)

    Inputs
    ------
    template
        Template space and specifications
    source_files
        List of input anatomical images
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

    ds_std2anat_xfm = pe.MapNode(
        DerivativesDataSink(
            base_directory=output_dir,
            to=image_type,
            mode='image',
            suffix='xfm',
            dismiss_entities=['desc'],
        ),
        iterfield=('in_file', 'from'),
        name='ds_std2anat_xfm',
        run_without_submitting=True,
    )

    ds_anat2std_xfm = pe.MapNode(
        DerivativesDataSink(
            base_directory=output_dir,
            mode='image',
            suffix='xfm',
            dismiss_entities=['desc'],
            **{'from': image_type},
        ),
        iterfield=('in_file', 'to'),
        name='ds_anat2std_xfm',
        run_without_submitting=True,
    )

    # fmt:off
    workflow.connect([
        (inputnode, ds_anat2std_xfm, [
            ('anat2std_xfm', 'in_file'),
            (('template', _combine_cohort), 'to'),
            ('source_files', 'source_file')]),
        (inputnode, ds_std2anat_xfm, [
            ('std2anat_xfm', 'in_file'),
            (('template', _combine_cohort), 'from'),
            ('source_files', 'source_file')]),
        (ds_anat2std_xfm, outputnode, [('out_file', 'anat2std_xfm')]),
        (ds_std2anat_xfm, outputnode, [('out_file', 'std2anat_xfm')]),
    ])
    # fmt:on

    return workflow


def init_ds_fs_registration_wf(
    *,
    output_dir: str,
    image_type: ty.Literal['T1w', 'T2w'],
    name: str = 'ds_fs_registration_wf',
):
    """
    Save rigid registration between subject anatomical template and either
    FreeSurfer T1.mgz or T2.mgz

    Parameters
    ----------
    output_dir : :obj:`str`
        Directory in which to save derivatives
    name : :obj:`str`
        Workflow name (default: ds_fs_registration_wf)

    Inputs
    ------
    source_files
        List of input anatomical images
    fsnative2anat_xfm
        LTA-style affine matrix translating from FreeSurfer-conformed
        subject space to T1/T2

    Outputs
    -------
    anat2fsnative_xfm
        LTA-style affine matrix translating from T1/T2 to
        FreeSurfer-conformed subject space
    fsnative2anat_xfm
        LTA-style affine matrix translating from FreeSurfer-conformed
        subject space to T1w

    """
    workflow = Workflow(name=name)

    inputnode = pe.Node(
        niu.IdentityInterface(fields=['source_files', 'fsnative2anat_xfm']),
        name='inputnode',
    )
    outputnode = pe.Node(
        niu.IdentityInterface(fields=['fsnative2anat_xfm', 'anat2fsnative_xfm']),
        name='outputnode',
    )

    from niworkflows.interfaces.nitransforms import ConcatenateXFMs

    # FS native space transforms
    lta2itk = pe.Node(ConcatenateXFMs(inverse=True), name='lta2itk', run_without_submitting=True)
    ds_anat_fsnative = pe.Node(
        DerivativesDataSink(
            base_directory=output_dir,
            mode='image',
            to='fsnative',
            suffix='xfm',
            extension='txt',
            **{'from': image_type},
        ),
        name='ds_anat_fsnative',
        run_without_submitting=True,
    )
    ds_fsnative_anat = pe.Node(
        DerivativesDataSink(
            base_directory=output_dir,
            mode='image',
            to=image_type,
            suffix='xfm',
            extension='txt',
            **{'from': 'fsnative'},
        ),
        name='ds_fsnative_anat',
        run_without_submitting=True,
    )

    # fmt:off
    workflow.connect([
        (inputnode, lta2itk, [('fsnative2anat_xfm', 'in_xfms')]),
        (inputnode, ds_anat_fsnative, [('source_files', 'source_file')]),
        (lta2itk, ds_anat_fsnative, [('out_inv', 'in_file')]),
        (inputnode, ds_fsnative_anat, [('source_files', 'source_file')]),
        (lta2itk, ds_fsnative_anat, [('out_xfm', 'in_file')]),
        (ds_fsnative_anat, outputnode, [('out_file', 'fsnative2anat_xfm')]),
        (ds_anat_fsnative, outputnode, [('out_file', 'anat2fsnative_xfm')]),
    ])
    # fmt:on
    return workflow


def init_ds_surfaces_wf(
    *,
    output_dir: str,
    surfaces: list[str],
    entities: dict[str, str] | None = None,
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
    entities : :class:`dict` of :class:`str`
        Entities to include in outputs
    name : :class:`str`
        Workflow name (default: ds_surfaces_wf)

    Inputs
    ------
    source_files
        List of input anatomical images
    ``<surface>``
        Left and right GIFTIs for each surface passed to ``surfaces``

    Outputs
    -------
    ``<surface>``
        Left and right GIFTIs in ``output_dir`` for each surface passed to ``surfaces``

    """
    workflow = Workflow(name=name)

    if entities is None:
        entities = {}

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
            elif surf == 'sphere_reg_dhcpAsym':
                ds_surf.inputs.space = 'dhcpAsym'
            elif surf == 'sphere_reg_msm':
                ds_surf.inputs.space, ds_surf.inputs.desc = 'fsLR', 'msmsulc'

        ds_surf.inputs.trait_set(**entities)

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
                # Original anat image
                'source_files',
                # anat-space images
                'anat_preproc',
                'anat_mask',
                'anat_dseg',
                'anat_tpms',
                # Template
                'ref_file',
                'anat2std_xfm',
                # Entities
                'space',
                'resolution',
            ]
        ),
        name='inputnode',
    )

    raw_sources = pe.Node(niu.Function(function=_bids_relative), name='raw_sources')
    raw_sources.inputs.bids_root = bids_root

    gen_ref = pe.Node(GenerateSamplingReference(), name='gen_ref', mem_gb=0.01)

    # Mask T1w preproc images
    mask_anat = pe.Node(ApplyMask(), name='mask_anat')

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
        (inputnode, mask_anat, [
            ('anat_preproc', 'in_file'),
            ('anat_mask', 'in_mask'),
        ]),
        (mask_anat, anat2std_t1w, [('out_file', 'input_image')]),
        (inputnode, anat2std_mask, [('anat_mask', 'input_image')]),
        (inputnode, anat2std_dseg, [('anat_dseg', 'input_image')]),
        (inputnode, anat2std_tpms, [('anat_tpms', 'input_image')]),
        (inputnode, gen_ref, [('anat_preproc', 'moving_image')]),
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
                ('resolution', 'resolution'),
            ])
            for n in (ds_std_t1w, ds_std_mask, ds_std_dseg, ds_std_tpms)
        ]
    )  # fmt:skip

    return workflow


def init_ds_fs_segs_wf(
    *,
    bids_root: str,
    output_dir: str,
    extra_entities: dict | None = None,
    name='ds_fs_segs_wf',
):
    """
    Set up a battery of datasinks to store derivatives in the right location.

    Parameters
    ----------
    bids_root : :obj:`str`
        Root path of BIDS dataset
    output_dir : :obj:`str`
        Directory in which to save derivatives
    extra_entities : :obj:`dict` or None
        Additional entities to add to filename
    name : :obj:`str`
        Workflow name (default: ds_anat_segs_wf)

    Inputs
    ------
    anat_fs_aparc
        FreeSurfer's aparc+aseg segmentation, in native anatomical space
    anat_fs_aseg
        FreeSurfer's aseg segmentation, in native anatomical space
    source_files
        List of input anatomical images
    """
    workflow = Workflow(name=name)

    inputnode = pe.Node(
        niu.IdentityInterface(
            fields=[
                'source_files',
                'anat_fs_aseg',
                'anat_fs_aparc',
            ]
        ),
        name='inputnode',
    )

    raw_sources = pe.Node(niu.Function(function=_bids_relative), name='raw_sources')
    raw_sources.inputs.bids_root = bids_root

    extra_entities = extra_entities or {}

    # Parcellations
    ds_anat_fsaseg = pe.Node(
        DerivativesDataSink(
            base_directory=output_dir,
            desc='aseg',
            suffix='dseg',
            compress=True,
            **extra_entities,
        ),
        name='ds_anat_fsaseg',
        run_without_submitting=True,
    )
    ds_anat_fsparc = pe.Node(
        DerivativesDataSink(
            base_directory=output_dir,
            desc='aparcaseg',
            suffix='dseg',
            compress=True,
            **extra_entities,
        ),
        name='ds_anat_fsparc',
        run_without_submitting=True,
    )

    workflow.connect([
        (inputnode, ds_anat_fsaseg, [('anat_fs_aseg', 'in_file'),
                                     ('source_files', 'source_file')]),
        (inputnode, ds_anat_fsparc, [('anat_fs_aparc', 'in_file'),
                                     ('source_files', 'source_file')]),
    ])  # fmt:skip

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
                'full_space',
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

    gen_full_space = pe.Node(
        niu.Function(function=_gen_full_space),
        name='gen_full_space',
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
        (spacesource, gen_full_space, [
            ('space', 'template'),
            ('cohort', 'cohort'),
        ]),
        (gen_full_space, outputnode, [('out', 'full_space')]),
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


def init_ds_surface_masks_wf(
    *,
    output_dir: str,
    mask_type: ty.Literal['cortex', 'roi', 'ribbon', 'brain'],
    entities: dict[str, str] | None = None,
    name='ds_surface_masks_wf',
) -> Workflow:
    """Save GIFTI surface masks.

    Parameters
    ----------
    output_dir : :class:`str`
        Directory in which to save derivatives
    mask_type : :class:`str`
        Type of mask to save
    entities : :class:`dict` of :class:`str`
        Entities to include in outputs
    name : :class:`str`
        Workflow name (default: ds_surface_masks_wf)

    Inputs
    ------
    source_files : list of lists of str
        List of lists of source files.
        Left hemisphere sources first, then right hemisphere sources.
    mask_files : list of str
        List of input mask files.
        Left hemisphere mask first, then right hemisphere mask.

    Outputs
    -------
    mask_files : list of str
        List of output mask files.
        Left hemisphere mask first, then right hemisphere mask.
    """
    workflow = Workflow(name=name)

    if entities is None:
        entities = {}

    inputnode = pe.Node(
        niu.IdentityInterface(fields=['mask_files', 'source_files']),
        name='inputnode',
    )
    outputnode = pe.JoinNode(
        niu.IdentityInterface(fields=['mask_files']), name='outputnode', joinsource='ds_itersource'
    )

    ds_itersource = pe.Node(
        niu.IdentityInterface(fields=['hemi']),
        name='ds_itersource',
        iterables=[('hemi', ['L', 'R'])],
    )

    sources = pe.Node(niu.Function(function=_bids_relative), name='sources')
    sources.inputs.bids_root = output_dir

    select_files = pe.Node(
        KeySelect(fields=['mask_file', 'sources'], keys=['L', 'R']),
        name='select_files',
        run_without_submitting=True,
    )

    ds_surf_mask = pe.Node(
        DerivativesDataSink(
            base_directory=output_dir,
            suffix='mask',
            desc=mask_type,
            extension='.label.gii',
            Type='Brain' if mask_type == 'brain' else 'ROI',
            **entities,
        ),
        name='ds_surf_mask',
        run_without_submitting=True,
    )

    workflow.connect([
        (inputnode, select_files, [
            ('mask_files', 'mask_file'),
            ('source_files', 'sources'),
        ]),
        (select_files, sources, [('sources', 'in_files')]),
        (ds_itersource, select_files, [('hemi', 'key')]),
        (ds_itersource, ds_surf_mask, [('hemi', 'hemi')]),
        (select_files, ds_surf_mask, [
            ('mask_file', 'in_file'),
            (('sources', _pop), 'source_file'),
        ]),
        (sources, ds_surf_mask, [('out', 'Sources')]),
        (ds_surf_mask, outputnode, [('out_file', 'mask_files')]),
    ])  # fmt: skip

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


def _gen_full_space(template, cohort=None):
    from nipype.interfaces.base import isdefined

    if cohort and isdefined(cohort):
        return f'{template}+{cohort}'

    return template


def _combine_cohort(in_template):
    if isinstance(in_template, str):
        template = in_template.split(':')[0]
        if 'cohort-' not in in_template:
            return template
        return f'{template}+{in_template.split("cohort-")[-1].split(":")[0]}'
    return [_combine_cohort(v) for v in in_template]


def _read_json(in_file):
    from json import loads
    from pathlib import Path

    return loads(Path(in_file).read_text())


def _pop(in_list):
    return in_list[0]

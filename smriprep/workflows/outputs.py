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
from nipype.pipeline import engine as pe
from nipype.interfaces import utility as niu
from niworkflows.interfaces.nibabel import ApplyMask
from niworkflows.engine.workflows import LiterateWorkflow as Workflow

from ..interfaces import DerivativesDataSink

BIDS_TISSUE_ORDER = ("GM", "WM", "CSF")


def init_anat_reports_wf(*, freesurfer, output_dir, name="anat_reports_wf"):
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
    from niworkflows.interfaces.reportlets.registration import (
        SimpleBeforeAfterRPT as SimpleBeforeAfter,
    )
    from niworkflows.interfaces.reportlets.masks import ROIsPlot
    from ..interfaces.templateflow import TemplateFlowSelect

    workflow = Workflow(name=name)

    inputfields = [
        "source_file",
        "t1w_conform_report",
        "t1w_preproc",
        "t1w_dseg",
        "t1w_mask",
        "template",
        "std_t1w",
        "std_mask",
        "subject_id",
        "subjects_dir",
    ]
    inputnode = pe.Node(niu.IdentityInterface(fields=inputfields), name="inputnode")

    seg_rpt = pe.Node(
        ROIsPlot(colors=["b", "magenta"], levels=[1.5, 2.5]), name="seg_rpt"
    )

    t1w_conform_check = pe.Node(
        niu.Function(function=_empty_report),
        name="t1w_conform_check",
        run_without_submitting=True,
    )

    ds_t1w_conform_report = pe.Node(
        DerivativesDataSink(
            base_directory=output_dir, desc="conform", datatype="figures"
        ),
        name="ds_t1w_conform_report",
        run_without_submitting=True,
    )

    ds_t1w_dseg_mask_report = pe.Node(
        DerivativesDataSink(
            base_directory=output_dir, suffix="dseg", datatype="figures"
        ),
        name="ds_t1w_dseg_mask_report",
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

    # Generate reportlets showing spatial normalization
    tf_select = pe.Node(
        TemplateFlowSelect(resolution=1), name="tf_select", run_without_submitting=True
    )
    norm_msk = pe.Node(
        niu.Function(
            function=_rpt_masks,
            output_names=["before", "after"],
            input_names=["mask_file", "before", "after", "after_mask"],
        ),
        name="norm_msk",
    )
    norm_rpt = pe.Node(SimpleBeforeAfter(), name="norm_rpt", mem_gb=0.1)
    norm_rpt.inputs.after_label = "Participant"  # after

    ds_std_t1w_report = pe.Node(
        DerivativesDataSink(
            base_directory=output_dir, suffix="T1w", datatype="figures"
        ),
        name="ds_std_t1w_report",
        run_without_submitting=True,
    )

    # fmt:off
    workflow.connect([
        (inputnode, tf_select, [(('template', _drop_cohort), 'template'),
                                (('template', _pick_cohort), 'cohort')]),
        (inputnode, norm_rpt, [('template', 'before_label')]),
        (inputnode, norm_msk, [('std_t1w', 'after'),
                               ('std_mask', 'after_mask')]),
        (tf_select, norm_msk, [('t1w_file', 'before'),
                               ('brain_mask', 'mask_file')]),
        (norm_msk, norm_rpt, [('before', 'before'),
                              ('after', 'after')]),
        (inputnode, ds_std_t1w_report, [
            (('template', _fmt), 'space'),
            ('source_file', 'source_file')]),
        (norm_rpt, ds_std_t1w_report, [('out_report', 'in_file')]),
    ])
    # fmt:on

    if freesurfer:
        from ..interfaces.reports import FSSurfaceReport

        recon_report = pe.Node(FSSurfaceReport(), name="recon_report")
        recon_report.interface._always_run = True

        ds_recon_report = pe.Node(
            DerivativesDataSink(
                base_directory=output_dir, desc="reconall", datatype="figures"
            ),
            name="ds_recon_report",
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


def init_anat_derivatives_wf(
    *,
    bids_root,
    freesurfer,
    num_t1w,
    output_dir,
    spaces,
    name="anat_derivatives_wf",
    tpm_labels=BIDS_TISSUE_ORDER,
):
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
    from niworkflows.interfaces.utility import KeySelect

    workflow = Workflow(name=name)

    inputnode = pe.Node(
        niu.IdentityInterface(
            fields=[
                "template",
                "source_files",
                "t1w_ref_xfms",
                "t1w_preproc",
                "t1w_mask",
                "t1w_dseg",
                "t1w_tpms",
                "anat2std_xfm",
                "std2anat_xfm",
                "t1w2fsnative_xfm",
                "fsnative2t1w_xfm",
                "surfaces",
                "t1w_fs_aseg",
                "t1w_fs_aparc",
            ]
        ),
        name="inputnode",
    )

    raw_sources = pe.Node(niu.Function(function=_bids_relative), name="raw_sources")
    raw_sources.inputs.bids_root = bids_root

    ds_t1w_preproc = pe.Node(
        DerivativesDataSink(base_directory=output_dir, desc="preproc", compress=True),
        name="ds_t1w_preproc",
        run_without_submitting=True,
    )
    ds_t1w_preproc.inputs.SkullStripped = False

    ds_t1w_mask = pe.Node(
        DerivativesDataSink(
            base_directory=output_dir, desc="brain", suffix="mask", compress=True
        ),
        name="ds_t1w_mask",
        run_without_submitting=True,
    )
    ds_t1w_mask.inputs.Type = "Brain"

    ds_t1w_dseg = pe.Node(
        DerivativesDataSink(base_directory=output_dir, suffix="dseg", compress=True),
        name="ds_t1w_dseg",
        run_without_submitting=True,
    )

    ds_t1w_tpms = pe.Node(
        DerivativesDataSink(base_directory=output_dir, suffix="probseg", compress=True),
        name="ds_t1w_tpms",
        run_without_submitting=True,
    )
    ds_t1w_tpms.inputs.label = tpm_labels

    # fmt:off
    workflow.connect([
        (inputnode, raw_sources, [('source_files', 'in_files')]),
        (inputnode, ds_t1w_preproc, [('t1w_preproc', 'in_file'),
                                     ('source_files', 'source_file')]),
        (inputnode, ds_t1w_mask, [('t1w_mask', 'in_file'),
                                  ('source_files', 'source_file')]),
        (inputnode, ds_t1w_tpms, [('t1w_tpms', 'in_file'),
                                  ('source_files', 'source_file')]),
        (inputnode, ds_t1w_dseg, [('t1w_dseg', 'in_file'),
                                  ('source_files', 'source_file')]),
        (raw_sources, ds_t1w_mask, [('out', 'RawSources')]),
    ])
    # fmt:on

    # Transforms
    if spaces.get_spaces(nonstandard=False, dim=(3,)):
        ds_std2t1w_xfm = pe.MapNode(
            DerivativesDataSink(
                base_directory=output_dir, to="T1w", mode="image", suffix="xfm"
            ),
            iterfield=("in_file", "from"),
            name="ds_std2t1w_xfm",
            run_without_submitting=True,
        )

        ds_t1w2std_xfm = pe.MapNode(
            DerivativesDataSink(
                base_directory=output_dir, mode="image", suffix="xfm", **{"from": "T1w"}
            ),
            iterfield=("in_file", "to"),
            name="ds_t1w2std_xfm",
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
        ])
        # fmt:on

    if num_t1w > 1:
        # Please note the dictionary unpacking to provide the from argument.
        # It is necessary because from is a protected keyword (not allowed as argument name).
        ds_t1w_ref_xfms = pe.MapNode(
            DerivativesDataSink(
                base_directory=output_dir,
                to="T1w",
                mode="image",
                suffix="xfm",
                extension="txt",
                **{"from": "orig"},
            ),
            iterfield=["source_file", "in_file"],
            name="ds_t1w_ref_xfms",
            run_without_submitting=True,
        )
        # fmt:off
        workflow.connect([
            (inputnode, ds_t1w_ref_xfms, [('source_files', 'source_file'),
                                          ('t1w_ref_xfms', 'in_file')]),
        ])
        # fmt:on

    # Write derivatives in standard spaces specified by --output-spaces
    if getattr(spaces, "_cached") is not None and spaces.cached.references:
        from niworkflows.interfaces.space import SpaceDataSource
        from niworkflows.interfaces.nibabel import GenerateSamplingReference
        from niworkflows.interfaces.fixes import (
            FixHeaderApplyTransforms as ApplyTransforms,
        )

        from ..interfaces.templateflow import TemplateFlowSelect

        spacesource = pe.Node(
            SpaceDataSource(), name="spacesource", run_without_submitting=True
        )
        spacesource.iterables = (
            "in_tuple",
            [(s.fullname, s.spec) for s in spaces.cached.get_standard(dim=(3,))],
        )

        gen_tplid = pe.Node(
            niu.Function(function=_fmt_cohort),
            name="gen_tplid",
            run_without_submitting=True,
        )

        select_xfm = pe.Node(
            KeySelect(fields=["anat2std_xfm"]),
            name="select_xfm",
            run_without_submitting=True,
        )
        select_tpl = pe.Node(
            TemplateFlowSelect(), name="select_tpl", run_without_submitting=True
        )

        gen_ref = pe.Node(GenerateSamplingReference(), name="gen_ref", mem_gb=0.01)

        # Mask T1w preproc images
        mask_t1w = pe.Node(ApplyMask(), name='mask_t1w')

        # Resample T1w-space inputs
        anat2std_t1w = pe.Node(
            ApplyTransforms(
                dimension=3,
                default_value=0,
                float=True,
                interpolation="LanczosWindowedSinc",
            ),
            name="anat2std_t1w",
        )

        anat2std_mask = pe.Node(
            ApplyTransforms(interpolation="MultiLabel"), name="anat2std_mask"
        )
        anat2std_dseg = pe.Node(
            ApplyTransforms(interpolation="MultiLabel"), name="anat2std_dseg"
        )
        anat2std_tpms = pe.MapNode(
            ApplyTransforms(
                dimension=3, default_value=0, float=True, interpolation="Gaussian"
            ),
            iterfield=["input_image"],
            name="anat2std_tpms",
        )

        ds_std_t1w = pe.Node(
            DerivativesDataSink(
                base_directory=output_dir,
                desc="preproc",
                compress=True,
            ),
            name="ds_std_t1w",
            run_without_submitting=True,
        )
        ds_std_t1w.inputs.SkullStripped = True

        ds_std_mask = pe.Node(
            DerivativesDataSink(
                base_directory=output_dir, desc="brain", suffix="mask", compress=True
            ),
            name="ds_std_mask",
            run_without_submitting=True,
        )
        ds_std_mask.inputs.Type = "Brain"

        ds_std_dseg = pe.Node(
            DerivativesDataSink(
                base_directory=output_dir, suffix="dseg", compress=True
            ),
            name="ds_std_dseg",
            run_without_submitting=True,
        )

        ds_std_tpms = pe.Node(
            DerivativesDataSink(
                base_directory=output_dir, suffix="probseg", compress=True
            ),
            name="ds_std_tpms",
            run_without_submitting=True,
        )

        # CRITICAL: the sequence of labels here (CSF-GM-WM) is that of the output of FSL-FAST
        #           (intensity mean, per tissue). This order HAS to be matched also by the ``tpms``
        #           output in the data/io_spec.json file.
        ds_std_tpms.inputs.label = tpm_labels
        # fmt:off
        workflow.connect([
            (inputnode, mask_t1w, [('t1w_preproc', 'in_file'),
                                   ('t1w_mask', 'in_mask')]),
            (mask_t1w, anat2std_t1w, [('out_file', 'input_image')]),
            (inputnode, anat2std_mask, [('t1w_mask', 'input_image')]),
            (inputnode, anat2std_dseg, [('t1w_dseg', 'input_image')]),
            (inputnode, anat2std_tpms, [('t1w_tpms', 'input_image')]),
            (inputnode, gen_ref, [('t1w_preproc', 'moving_image')]),
            (inputnode, select_xfm, [
                ('anat2std_xfm', 'anat2std_xfm'),
                ('template', 'keys')]),
            (spacesource, gen_tplid, [('space', 'template'),
                                      ('cohort', 'cohort')]),
            (gen_tplid, select_xfm, [('out', 'key')]),
            (spacesource, select_tpl, [('space', 'template'),
                                       ('cohort', 'cohort'),
                                       (('resolution', _no_native), 'resolution')]),
            (spacesource, gen_ref, [(('resolution', _is_native), 'keep_native')]),
            (select_tpl, gen_ref, [('t1w_file', 'fixed_image')]),
            (anat2std_t1w, ds_std_t1w, [('output_image', 'in_file')]),
            (anat2std_mask, ds_std_mask, [('output_image', 'in_file')]),
            (anat2std_dseg, ds_std_dseg, [('output_image', 'in_file')]),
            (anat2std_tpms, ds_std_tpms, [('output_image', 'in_file')]),
            (select_tpl, ds_std_mask, [(('brain_mask', _drop_path), 'RawSources')]),
        ])

        workflow.connect(
            # Connect apply transforms nodes
            [
                (gen_ref, n, [('out_file', 'reference_image')])
                for n in (anat2std_t1w, anat2std_mask, anat2std_dseg, anat2std_tpms)
            ]
            + [
                (select_xfm, n, [('anat2std_xfm', 'transforms')])
                for n in (anat2std_t1w, anat2std_mask, anat2std_dseg, anat2std_tpms)
            ]
            # Connect the source_file input of these datasinks
            + [
                (inputnode, n, [('source_files', 'source_file')])
                for n in (ds_std_t1w, ds_std_mask, ds_std_dseg, ds_std_tpms)
            ]
            # Connect the space input of these datasinks
            + [
                (spacesource, n, [
                    ('space', 'space'), ('cohort', 'cohort'), ('resolution', 'resolution')
                ])
                for n in (ds_std_t1w, ds_std_mask, ds_std_dseg, ds_std_tpms)
            ]
        )
        # fmt:on

    if not freesurfer:
        return workflow

    from niworkflows.interfaces.nitransforms import ConcatenateXFMs
    from niworkflows.interfaces.surf import Path2BIDS

    # FS native space transforms
    lta2itk_fwd = pe.Node(
        ConcatenateXFMs(), name="lta2itk_fwd", run_without_submitting=True
    )
    lta2itk_inv = pe.Node(
        ConcatenateXFMs(), name="lta2itk_inv", run_without_submitting=True
    )
    ds_t1w_fsnative = pe.Node(
        DerivativesDataSink(
            base_directory=output_dir,
            mode="image",
            to="fsnative",
            suffix="xfm",
            extension="txt",
            **{"from": "T1w"},
        ),
        name="ds_t1w_fsnative",
        run_without_submitting=True,
    )
    ds_fsnative_t1w = pe.Node(
        DerivativesDataSink(
            base_directory=output_dir,
            mode="image",
            to="T1w",
            suffix="xfm",
            extension="txt",
            **{"from": "fsnative"},
        ),
        name="ds_fsnative_t1w",
        run_without_submitting=True,
    )
    # Surfaces
    name_surfs = pe.MapNode(
        Path2BIDS(), iterfield="in_file", name="name_surfs", run_without_submitting=True
    )
    ds_surfs = pe.MapNode(
        DerivativesDataSink(base_directory=output_dir, extension=".surf.gii"),
        iterfield=["in_file", "hemi", "suffix"],
        name="ds_surfs",
        run_without_submitting=True,
    )
    # Parcellations
    ds_t1w_fsaseg = pe.Node(
        DerivativesDataSink(
            base_directory=output_dir, desc="aseg", suffix="dseg", compress=True
        ),
        name="ds_t1w_fsaseg",
        run_without_submitting=True,
    )
    ds_t1w_fsparc = pe.Node(
        DerivativesDataSink(
            base_directory=output_dir, desc="aparcaseg", suffix="dseg", compress=True
        ),
        name="ds_t1w_fsparc",
        run_without_submitting=True,
    )

    # fmt:off
    workflow.connect([
        (inputnode, lta2itk_fwd, [('t1w2fsnative_xfm', 'in_xfms')]),
        (inputnode, lta2itk_inv, [('fsnative2t1w_xfm', 'in_xfms')]),
        (inputnode, ds_t1w_fsnative, [('source_files', 'source_file')]),
        (lta2itk_fwd, ds_t1w_fsnative, [('out_xfm', 'in_file')]),
        (inputnode, ds_fsnative_t1w, [('source_files', 'source_file')]),
        (lta2itk_inv, ds_fsnative_t1w, [('out_xfm', 'in_file')]),
        (inputnode, name_surfs, [('surfaces', 'in_file')]),
        (inputnode, ds_surfs, [('surfaces', 'in_file'),
                               ('source_files', 'source_file')]),
        (name_surfs, ds_surfs, [('hemi', 'hemi'),
                                ('suffix', 'suffix')]),
        (inputnode, ds_t1w_fsaseg, [('t1w_fs_aseg', 'in_file'),
                                    ('source_files', 'source_file')]),
        (inputnode, ds_t1w_fsparc, [('t1w_fs_aparc', 'in_file'),
                                    ('source_files', 'source_file')]),
    ])
    # fmt:on
    return workflow


def _bids_relative(in_files, bids_root):
    from pathlib import Path

    if not isinstance(in_files, (list, tuple)):
        in_files = [in_files]
    in_files = [str(Path(p).relative_to(bids_root)) for p in in_files]
    return in_files


def _rpt_masks(mask_file, before, after, after_mask=None):
    from os.path import abspath
    import nibabel as nb

    msk = nb.load(mask_file).get_fdata() > 0
    bnii = nb.load(before)
    nb.Nifti1Image(bnii.get_fdata() * msk, bnii.affine, bnii.header).to_filename(
        "before.nii.gz"
    )
    if after_mask is not None:
        msk = nb.load(after_mask).get_fdata() > 0

    anii = nb.load(after)
    nb.Nifti1Image(anii.get_fdata() * msk, anii.affine, anii.header).to_filename(
        "after.nii.gz"
    )
    return abspath("before.nii.gz"), abspath("after.nii.gz")


def _drop_cohort(in_template):
    if isinstance(in_template, str):
        return in_template.split(":")[0]
    return [_drop_cohort(v) for v in in_template]


def _pick_cohort(in_template):
    if isinstance(in_template, str):
        if "cohort-" not in in_template:
            from nipype.interfaces.base import Undefined

            return Undefined
        return in_template.split("cohort-")[-1].split(":")[0]
    return [_pick_cohort(v) for v in in_template]


def _fmt(in_template):
    return in_template.replace(":", "_")


def _empty_report(in_file=None):
    from pathlib import Path
    from nipype.interfaces.base import isdefined

    if in_file is not None and isdefined(in_file):
        return in_file

    out_file = Path("tmp-report.html").absolute()
    out_file.write_text(
        """\
                <h4 class="elem-title">A previously computed T1w template was provided.</h4>
"""
    )
    return str(out_file)


def _is_native(value):
    return value == "native"


def _no_native(value):
    try:
        return int(value)
    except Exception:
        return 1


def _drop_path(in_path):
    from pathlib import Path
    from templateflow.conf import TF_HOME

    return str(Path(in_path).relative_to(TF_HOME))


def _fmt_cohort(template, cohort=None):
    from nipype.interfaces.base import isdefined

    if cohort and isdefined(cohort):
        return f"{template}:cohort-{cohort}"
    return template


def _combine_cohort(in_template):
    if isinstance(in_template, str):
        template = in_template.split(":")[0]
        if "cohort-" not in in_template:
            return template
        return f"{template}+{in_template.split('cohort-')[-1].split(':')[0]}"
    return [_combine_cohort(v) for v in in_template]

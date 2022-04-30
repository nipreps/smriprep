# -*- coding: utf-8 -*-
# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
"""
The FastSufer module provides basic functions
for running FastSurfer CNN and surface processing.

"""
from ast import BoolOp
from genericpath import exists
import os
from xmlrpc.client import Boolean

from nipype.interfaces.base import (
    CommandLine,
    Directory,
    CommandLineInputSpec,
    OutputMultiPath,
    isdefined,
    TraitedSpec,
    BaseInterface,
    BaseInterfaceInputSpec,
    File,
    PackageInfo,
)
from nipype.interfaces.base.traits_extension import traits
from nipype.interfaces.io import IOBase


class FastSInputSpec(CommandLineInputSpec):
    r"""
    Required arguments
    ==================

    sd
        Output directory
    sid
        Subject ID for directory inside ``sd`` to be created
    t1
        T1 full head input, not bias corrected, global path.
        The 'network was trained with conformed images
        UCHAR, 256 x 256 x 256, 1 mm voxels and standard slice orientation.
        These specifications are checked in the ``eval.py`` script and the image
        is automatically conformed if it does not comply.
    fs_license
        Path to FreeSurfer license key file.


    Optional arguments
    ==================

    Network specific arguments
    --------------------------
    seg
        Global path with filename of segmentation
        (where and under which name to store it).
        Default location
            ``$SUBJECTS_DIR/$sid/mri/aparc.DKTatlas+aseg.deep.mgz``
    weights_sag
        Pretrained weights of sagittal network.
        Default
            ``../checkpoints/Sagittal_Weights_FastSurferCNN/ckpts/Epoch_30_training_state.pkl``
    weights_ax
        Pretrained weights of axial network.
        Default
            ``../checkpoints/Axial_Weights_FastSurferCNN/ckpts/Epoch_30_training_state.pkl``
    weights_cor
        Pretrained weights of coronal network.
        Default
            ``../checkpoints/Coronal_Weights_FastSurferCNN/ckpts/Epoch_30_training_state.pkl``
    seg_log
        Name and location for the log-file for the segmentation (FastSurferCNN).
        Default '$SUBJECTS_DIR/$sid/scripts/deep-seg.log'
    clean_seg
        Flag to clean up FastSurferCNN segmentation
    run_viewagg_on
        Define where the view aggregation should be run on.
        By default, the program checks if you have enough memory to run
        the view aggregation on the gpu. The total memory is considered for this decision.
        If this fails, or you actively overwrote the check with setting
        ``run_viewagg_on cpu``, view agg is run on the cpu.
        Equivalently, if you define ``--run_viewagg_on gpu``, view agg will be run on the gpu
        (no memory check will be done).
    no_cuda
        Flag to disable CUDA usage in FastSurferCNN (no GPU usage, inference on CPU)
    batch
        Batch size for inference. Default 16. Lower this to reduce memory requirement
    order
        Order of interpolation for mri_convert T1 before segmentation
        ``(0=nearest, 1=linear(default), 2=quadratic, 3=cubic)``


    Surface pipeline arguments
    --------------------------
    fstess
        Use ``mri_tesselate`` instead of marching cube (default) for surface creation
    fsqsphere
        Use FreeSurfer default instead of
        novel spectral spherical projection for qsphere
    fsaparc
        Use FS aparc segmentations in addition to DL prediction
        (slower in this case and usually the mapped ones from the DL prediction are fine)
    surfreg
        Create Surface-Atlas ``sphere.reg`` registration with FreeSurfer
        (for cross-subject correspondence or other mappings)
    parallel
        Run both hemispheres in parallel
    threads
        Set openMP and ITK threads


    Other
    ----
    py
        which python version to use.
        Default ``python3.6``
    seg_only
        only run FastSurferCNN
        (generate segmentation, do not run the surface pipeline)
    surf_only
        only run the surface pipeline ``recon_surf``.
        The segmentation created by FastSurferCNN must already exist in this case.


    """
    sd = Directory(
        exists=True,
        argstr="--sd %s",
        mandatory=True,
        desc="Subjects directory"
    )
    sid = traits.String(
        exists=True,
        argstr="--sid %s",
        mandatory=True,
        desc="Subject ID"
    )
    t1 = File(
        exists=True,
        mandatory=True,
        argstr="--t1 %s",
        desc="T1 full head input (not bias corrected, global path)"
    )
    fs_license = File(
        exists=True,
        mandatory=True,
        argstr="--fs_license %s",
        desc="Path to FreeSurfer license key file."
    )
    seg = File(
        exists=True,
        mandatory=False,
        argstr="--seg %s",
        desc="Global path with filename of segmentation"
    )
    weights_sag = File(
        exists=True,
        mandatory=False,
        default="../checkpoints/Sagittal_Weights_FastSurferCNN/ckpts/Epoch_30_training_state.pkl",
        usedefault=False, argstr="--weights_sag %s",
        desc="Pretrained weights of sagittal network"
    )
    weights_ax = File(
        exists=True,
        mandatory=False,
        default="../checkpoints/Axial_Weights_FastSurferCNN/ckpts/Epoch_30_training_state.pkl",
        usedefault=False,
        argstr="--weights_ax %s",
        desc="Pretrained weights of axial network"
    )
    weights_cor = File(
        exists=True,
        mandatory=False,
        default="../checkpoints/Coronal_Weights_FastSurferCNN/ckpts/Epoch_30_training_state.pkl",
        usedefault=False,
        argstr="--weights_cor %s",
        desc="Pretrained weights of coronal network"
    )
    seg_log = File(
        exists=True,
        mandatory=False,
        argstr="--seg_log %s",
        desc="Name and location for the log-file for the segmentation (FastSurferCNN)."
    )
    clean_seg = traits.Bool(
        False,
        mandatory=False,
        usedefault=False,
        argstr="--clean_seg",
        desc="Flag to clean up FastSurferCNN segmentation"
    )
    run_viewagg_on = File(
        exists=True,
        mandatory=False,
        argstr="--run_viewagg_on %s",
        desc="Define where the view aggregation should be run on."
    )
    no_cuda = traits.Bool(
        False,
        mandatory=False,
        usedefault=False,
        argstr="--no_cuda",
        desc="Flag to disable CUDA usage in FastSurferCNN (no GPU usage, inference on CPU)"
    )
    batch = traits.Int(
        16,
        usedefault=True,
        mandatory=False,
        argstr="--batch %d",
        desc="Batch size for inference. default=16. Lower this to reduce memory requirement"
    )
    order = traits.Int(
        1,
        mandatory=False,
        argstr="--order %d",
        usedefault=True,
        desc="""Order of interpolation for mri_convert T1 before segmentation
        (0=nearest, 1=linear(default), 2=quadratic, 3=cubic)"""
    )
    fstess = traits.Bool(
        False,
        usedefault=False,
        mandatory=False,
        argstr="--fstess",
        desc="Use mri_tesselate instead of marching cube (default) for surface creation"
    )
    fsqsphere = traits.Bool(
        False,
        usedefault=False,
        mandatory=False,
        argstr="--fsqsphere",
        desc="Use FreeSurfer default instead of novel spectral spherical projection for qsphere"
    )
    fsaparc = traits.Bool(
        False,
        usedefault=False,
        mandatory=False,
        argstr="--fsaparc",
        desc="Use FS aparc segmentations in addition to DL prediction"
    )
    surfreg = traits.Bool(
        True,
        usedefault=True,
        mandatory=False,
        argstr="--surfreg",
        desc="""Create Surface-Atlas (sphere.reg) registration with FreeSurfer
        (for cross-subject correspondence or other mappings)"""
    )
    parallel = traits.Bool(
        True,
        usedefault=True,
        mandatory=False,
        argstr="--parallel",
        desc="Run both hemispheres in parallel"
    )
    threads = traits.Int(
        4,
        usedefault=True,
        mandatory=False,
        argstr="--threads %d",
        desc="Set openMP and ITK threads to"
    )
    py = traits.String(
        "python3.6",
        usedefault=True,
        mandatory=False,
        argstr="--py %s",
        desc="which python version to use. default=python3.6"
    )
    seg_only = traits.Bool(
        False,
        usedefault=False,
        mandatory=False,
        argstr="--seg_only",
        desc="only run FastSurferCNN (generate segmentation, do not surface)"
    )
    surf_only = traits.Bool(
        False,
        usedefault=False,
        mandatory=False,
        argstr="--surf_only",
        desc="only run the surface pipeline recon_surf."
    )


class FastSTraitedOutputSpec(TraitedSpec):
    r"""
    Outputs directory within the FastSurfer subjects_dir/subject_id/
    with structure equivalent to Freesurfer

    """
    outputs = Directory(
        exists=True,
        desc="FastSurfer CNN + Surface Pipeline equivalent of recon-all outputs"
    )


class FastSurfSourceInputSpec(BaseInterfaceInputSpec):
    sd = Directory(
        exists=True,
        argstr="--sd %s",
        mandatory=True,
        desc="Subjects directory"
    )
    sid = traits.String(
        exists=True,
        argstr="--sid %s",
        mandatory=True,
        desc="Subject ID"
    )
    t1 = File(
        exists=True,
        mandatory=True,
        argstr="--t1 %s",
        desc="T1 full head input (not bias corrected, global path)"
    )
    fs_license = File(
        exists=True,
        mandatory=True,
        argstr="--fs_license %s",
        desc="Path to FreeSurfer license key file."
    )


class FastSurfSourceOutputSpec(TraitedSpec):
    T1 = File(
        exists=True,
        desc="Intensity normalized whole-head volume",
        loc="mri"
    )
    aseg = File(
        exists=True,
        loc="mri",
        desc="Volumetric map of regions from automatic segmentation",
    )
    brain = File(
        exists=True,
        desc="Intensity normalized brain-only volume",
        loc="mri"
    )
    brainmask = File(
        exists=True,
        desc="Skull-stripped (brain-only) volume",
        loc="mri"
    )
    filled = File(
        exists=True,
        desc="Subcortical mass volume",
        loc="mri"
    )
    norm = File(
        exists=True,
        desc="Normalized skull-stripped volume",
        loc="mri"
    )
    nu = File(
        exists=True,
        desc="Non-uniformity corrected whole-head volume",
        loc="mri"
    )
    orig = File(
        exists=True,
        desc="Base image conformed to FastSurfer space",
        loc="mri"
    )
    orig_nu = File(
        exists=True,
        desc="Base image conformed to Fastsurfer space and nonuniformity corrected",
        loc="mri"
    )
    rawavg = File(
        exists=True,
        desc="Volume formed by averaging input images",
        loc="mri"
    )
    ribbon = OutputMultiPath(
        File(exists=True),
        desc="Volumetric maps of cortical ribbons",
        loc="mri",
        altkey="*ribbon",
    )
    wm = File(
        exists=True,
        desc="Segmented white-matter volume",
        loc="mri"
    )
    wm_asegedit = OutputMultiPath(
        File(exists=True),
        desc="Edited white matter volume post-aseg",
        loc="mri",
        altkey="mri_nu_correct.mni"
    )
    wmparc = File(
        exists=True,
        loc="mri",
        desc="Aparc parcellation projected into subcortical white matter",
    )
    wmparc_mapped = OutputMultiPath(
        exists=True,
        loc="mri",
        desc="DKT atlas mapped Aparc into subcortical white matter",
        altkey="wmparc.DKTatlas.mapped"
    )
    mni_log = OutputMultiPath(
        File(exists=True),
        desc="Non-uniformity correction log",
        loc="mri",
        altkey="mri_nu_correct.mni"
    )
    mni_log_bak = OutputMultiPath(
        File(exists=True),
        desc="Non-uniformity correction log bak",
        loc="mri",
        altkey="mri_nu_correct.mni"
    )
    curv = OutputMultiPath(
        File(exists=True),
        desc="Maps of surface curvature",
        loc="surf"
    )
    avg_curv = OutputMultiPath(
        File(exists=True),
        desc="Average atlas curvature,sampled to subject",
        loc="surf",
    )
    inflated = OutputMultiPath(
        File(exists=True),
        desc="Inflated surface meshes",
        loc="surf"
    )
    pial = OutputMultiPath(
        File(exists=True),
        desc="Gray matter/pia mater surface meshes",
        loc="surf"
    )
    area_pial = OutputMultiPath(
        File(exists=True),
        desc="Mean area of triangles each vertex on the pial surface is "
        "associated with",
        loc="surf",
        altkey="area.pial",
    )
    curv_pial = OutputMultiPath(
        File(exists=True),
        desc="Curvature of pial surface",
        loc="surf",
        altkey="curv.pial",
    )
    smoothwm = OutputMultiPath(
        File(exists=True),
        loc="surf",
        desc="Smoothed original surface meshes"
    )
    sphere = OutputMultiPath(
        File(exists=True),
        desc="Spherical surface meshes",
        loc="surf"
    )
    sulc = OutputMultiPath(
        File(exists=True),
        desc="Surface maps of sulcal depth",
        loc="surf"
    )
    thickness = OutputMultiPath(
        File(exists=True),
        loc="surf",
        desc="Surface maps of cortical thickness"
    )
    volume = OutputMultiPath(
        File(exists=True),
        desc="Surface maps of cortical volume",
        loc="surf"
    )
    white = OutputMultiPath(
        File(exists=True),
        desc="White/gray matter surface meshes",
        loc="surf"
    )
    jacobian_white = OutputMultiPath(
        File(exists=True),
        desc="Distortion required to register to spherical atlas",
        loc="surf",
    )
    graymid = OutputMultiPath(
        File(exists=True),
        desc="Graymid/midthickness surface meshes",
        loc="surf",
        altkey=["graymid", "midthickness"],
    )
    defects = OutputMultiPath(
        File(exists=True),
        desc="Defects",
        loc="surf",
        altkey=["defect_borders", "defect_chull", "defect_labels"],
    )
    nofix = OutputMultiPath(
        File(exists=True),
        desc="Pre-tessellation original surface",
        loc="surf",
        altkey=["nofix"],
    )
    label = OutputMultiPath(
        File(exists=True),
        desc="Volume and surface label files",
        loc="label",
        altkey="*label",
    )
    annot = OutputMultiPath(
        File(exists=True),
        desc="Surface annotation files",
        loc="label",
        altkey="*annot"
    )
    aparc_ctab = OutputMultiPath(
        File(exists=True),
        loc="label",
        altkey="aparc.annot.mapped.ctab",
        desc="Aparc parcellation annotation ctab file",
    )
    mapped_024 = OutputMultiPath(
        File(exists=True),
        loc="label",
        altkey="mapped*024",
        desc="Mapped label files",
    )
    cortex = OutputMultiPath(
        File(exists=True),
        loc="label",
        altkey="cortex",
        desc="Cortex class label files",
    )
    aparc_aseg = OutputMultiPath(
        File(exists=True),
        loc="mri",
        altkey="aparc?aseg",
        desc="Aparc parcellation projected into aseg volume",
    )
    aparc_dkt_aseg = OutputMultiPath(
        File(exists=True),
        loc="mri",
        altkey="aparc.DKTatlas*aseg*",
        desc="Aparc parcellation from DKT atlas projected into aseg volume",
    )
    segment_dat = OutputMultiPath(
        File(exists=True),
        loc="mri",
        altkey="segment_dat",
        desc="Segmentation .dat files",
    )
    filled_pretess = OutputMultiPath(
        File(exists=True),
        loc="mri",
        altkey="filled*pretess*",
        desc="Pre-tessellation filled volume files",
    )
    sphere_reg = OutputMultiPath(
        File(exists=True),
        loc="surf",
        altkey="sphere.reg",
        desc="Spherical registration file",
    )
    preaparc = OutputMultiPath(
        File(exists=True),
        loc="surf",
        altkey="preaparc",
        desc="Pre-Aparc files",
    )
    aseg_stats = OutputMultiPath(
        File(exists=True),
        loc="stats",
        altkey="aseg",
        desc="Automated segmentation statistics file",
    )
    wmparc_stats = OutputMultiPath(
        File(exists=True),
        loc="stats",
        altkey="wmparc.DKTatlas.mapped",
        desc="White matter parcellation statistics file",
    )
    aparc_stats = OutputMultiPath(
        File(exists=True),
        loc="stats",
        altkey="aparc.DKTatlas.mapped",
        desc="Aparc parcellation statistics files",
    )
    curv_stats = OutputMultiPath(
        File(exists=True),
        loc="stats",
        altkey="curv",
        desc="Curvature statistics files"
    )
    w_g_stats = OutputMultiPath(
        File(exists=True),
        loc="stats",
        altkey="w*g.pct",
        desc="White minus gray statistics files"
    )
    aseg_presurf_stats = OutputMultiPath(
        File(exists=True),
        loc="stats",
        altkey="aseg.presurf.hypos",
        desc="Automated segmentation pre-surface recon statistics files"
    )


class FastSurferSource(IOBase):
    """Generates FastSurfer subject info from their directories.

    """

    input_spec = FastSurfSourceInputSpec
    output_spec = FastSurfSourceOutputSpec
    _always_run = True
    _additional_metadata = ["loc", "altkey"]

    def _get_files(self, path, key, dirval, altkey=None):
        globsuffix = ""
        if dirval == "mri":
            globsuffix = ".mgz"
            if key in ("mni_log"):
                globsuffix = ".mgz"
            elif key in ("mni_log_bak"):
                globsuffix = ".log.bak"
        elif dirval == "stats":
            globsuffix = ".stats"
        globprefix = ""
        if dirval in ("surf", "label", "stats"):
            globprefix = "?h."
        if key in ("aseg_stats", "aseg_presurf_stats", "wmparc_stats"):
            globprefix = ""
        elif key == "ribbon":
            globprefix = "*"
        elif key == "aparc_ctab":
            globprefix = ""
            globsuffix = ""
        elif key in ("nofix", "defects", "preaparc"):
            globsuffix = "*"
        keys = ensure_list(altkey) if altkey else [key]
        globfmt = os.path.join(path, dirval, "".join((globprefix, "{}", globsuffix)))
        return [
            os.path.abspath(f) for key in keys for f in glob.glob(globfmt.format(key))
        ]

    def _list_outputs(self):
        subjects_dir = self.inputs.subjects_dir
        subject_path = os.path.join(subjects_dir, self.inputs.subject_id)
        output_traits = self._outputs()
        outputs = output_traits.get()
        for k in list(outputs.keys()):
            val = self._get_files(
                subject_path,
                k,
                output_traits.traits()[k].loc,
                output_traits.traits()[k].altkey,
            )
            if val:
                outputs[k] = simplify_list(val)
        return outputs


class FastSCommand(CommandLine):
    r"""
    Wraps FastSurfer command for segmentation and surface processing::

        $ /fastsurfer/run_fastsurfer.sh --fs_license /fs60/license \
        --t1 /data/sub-<label>/ses-<label>/anat/sub-<label>_ses-<label>_acq-<label>_T1w.nii.gz \
        --sid sub-<label> --sd /output

    """

    input_spec = FastSInputSpec
    output_spec = FastSurfSourceOutputSpec
    _cmd = '/fastsurfer/run_fastsurfer.sh'

    def _list_outputs(self):
        outputs = self.output_spec().get()
        return outputs

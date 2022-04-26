# -*- coding: utf-8 -*-
# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
"""The FastSufer module provides basic functions
for running FastSurfer CNN and surface processing.

Examples
--------
See the docstrings for the individual classes for 'working' examples.

"""
from ast import BoolOp
from genericpath import exists
import os
from xmlrpc.client import Boolean

from nipype.interfaces.base import (
    CommandLine,
    Directory,
    CommandLineInputSpec,
    isdefined,
    TraitedSpec,
    File,
    PackageInfo,
)
from nipype.interfaces.base.traits_extension import traits
__docformat__ = "restructuredtext"


class FastSInputSpec(CommandLineInputSpec):
    """
    Required arguments
    ------------------
    --sd: Output directory $SUBJECTS_DIR
    --sid: Subject ID for directory inside $SUBJECTS_DIR to be created
    --t1: T1 full head input (not bias corrected, global path).
      The network was trained with conformed images (UCHAR, 256x256x256, 
      1 mm voxels and standard slice orientation).
      These specifications are checked in the eval.py script and the image
      is automatically conformed if it does not comply.
    --fs_license: Path to FreeSurfer license key file.
      Register at https://surfer.nmr.mgh.harvard.edu/registration.html
      to obtain it if you do not have FreeSurfer installed so far.

    Optional arguments
    ------------------
    Network specific arguments:
    --seg: Global path with filename of segmentation
      (where and under which name to store it).
      Default location:
          $SUBJECTS_DIR/$sid/mri/aparc.DKTatlas+aseg.deep.mgz
    --weights_sag: Pretrained weights of sagittal network.
      Default:
          ../checkpoints/Sagittal_Weights_FastSurferCNN/ckpts/Epoch_30_training_state.pkl
    --weights_ax: Pretrained weights of axial network.
      Default:
       ../checkpoints/Axial_Weights_FastSurferCNN/ckpts/Epoch_30_training_state.pkl
    --weights_cor: Pretrained weights of coronal network.
      Default: ../checkpoints/Coronal_Weights_FastSurferCNN/ckpts/Epoch_30_training_state.pkl
    --seg_log: Name and location for the log-file for the segmentation (FastSurferCNN).
      Default: $SUBJECTS_DIR/$sid/scripts/deep-seg.log
    --clean_seg: Flag to clean up FastSurferCNN segmentation
    --run_viewagg_on: Define where the view aggregation should be run on.
      By default, the program checks if you have enough memory to run
      the view aggregation on the gpu. The total memory is considered for this decision.
      If this fails, or you actively overwrote the check with setting
      "--run_viewagg_on cpu", view agg is run on the cpu.
      Equivalently, if you define "--run_viewagg_on gpu", view agg will be run on the gpu
      (no memory check will be done).
    --no_cuda: Flag to disable CUDA usage in FastSurferCNN (no GPU usage, inference on CPU)
    --batch: Batch size for inference. Default: 16. Lower this to reduce memory requirement
    --order: Order of interpolation for mri_convert T1 before segmentation
      (0=nearest, 1=linear(default), 2=quadratic, 3=cubic)

    Surface pipeline arguments:
    --fstess: Use mri_tesselate instead of marching cube (default) for surface creation
    --fsqsphere: Use FreeSurfer default instead of
      novel spectral spherical projection for qsphere
    --fsaparc: Use FS aparc segmentations in addition to DL prediction
      (slower in this case and usually the mapped ones from the DL prediction are fine)
    --surfreg: Create Surface-Atlas (sphere.reg) registration with FreeSurfer
      (for cross-subject correspondence or other mappings)
    --parallel: Run both hemispheres in parallel
    --threads: Set openMP and ITK threads

    Other:
    --py: which python version to use. Default: python3.6
    --seg_only: only run FastSurferCNN
      (generate segmentation, do not run the surface pipeline)
    --surf_only: only run the surface pipeline recon_surf.
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
    """
    Outputs directory within the FastSurfer subjects_dir/subject_id/
      with structure equivalent to Freesurfer
    """
    outputs = Directory(
        exists=True,
        desc="FastSurfer CNN + Surface Pipeline equivalent of recon-all outputs"
    )


class FastSCommand(CommandLine):
    input_spec = FastSInputSpec
    output_spec = FastSTraitedOutputSpec
    _cmd = '/opt/FastSurfer/run_fastsurfer.sh'

    def _list_outputs(self):
        outputs = self.output_spec().get()
        return outputs

from pathlib import Path

from nipype.interfaces.base import (
    CommandLine,
    CommandLineInputSpec,
    File,
    TraitedSpec,
    traits,
)


class MSMInputSpec(CommandLineInputSpec):
    in_mesh = File(
        exists=True,
        mandatory=True,
        argstr='--inmesh=%s',
        desc='input mesh (available formats: VTK, ASCII, GIFTI). Needs to be a sphere',
    )
    out_base = File(
        name_source=['in_mesh'],
        name_template='%s_msm',
        argstr='--out=%s',
        desc='output basename',
    )
    reference_mesh = File(
        exists=True,
        argstr='--refmesh=%s',
        desc='reference mesh (available formats: VTK, ASCII, GIFTI). Needs to be a sphere.'
        'If not included algorithm assumes reference mesh is equivalent input',
    )
    in_data = File(
        exists=True,
        argstr='--indata=%s',
        desc='scalar or multivariate data for input - can be ASCII (.asc,.dpv,.txt) '
        'or GIFTI (.func.gii or .shape.gii)',
    )
    reference_data = File(
        exists=True,
        argstr='--refdata=%s',
        desc='scalar or multivariate data for reference - can be ASCII (.asc,.dpv,.txt) '
        'or GIFTI (.func.gii or .shape.gii)',
    )
    transformed_mesh = File(
        exists=True,
        argstr='--trans=%s',
        desc='Transformed source mesh (output of a previous registration). '
        'Use this to initialise the current registration.',
    )
    in_register = File(
        exists=True,
        argstr='--in_register=%s',
        desc='Input mesh at data resolution. Used to resample data onto input mesh if data '
        'is supplied at a different resolution. Note this mesh HAS to be in alignment with '
        'either the input_mesh of (if supplied) the transformed source mesh. '
        'Use with supreme caution.',
    )
    in_weight = File(
        exists=True,
        argstr='--inweight=%s',
        desc='cost function weighting for input - weights data in these vertices when calculating '
        'similarity (ASCII or GIFTI). Can be multivariate provided dimension equals that of data',
    )
    reference_weight = File(
        exists=True,
        argstr='--refweight=%s',
        desc='cost function weighting for reference - weights data in these vertices when '
        'calculating similarity (ASCII or GIFTI). Can be multivariate provided dimension '
        'equals that of data',
    )
    output_format = traits.Enum(
        'GIFTI',
        'VTK',
        'ASCII',
        'ASCII_MAT',
        argstr='--format=%s',
        desc='format of output files',
    )
    config_file = File(
        exists=True,
        argstr='--conf=%s',
        desc='configuration file',
    )
    levels = traits.Int(
        argstr='--levels=%d',
        desc='number of resolution levels (default = number of resolution levels specified '
        'by --opt in config file)',
    )
    smooth_output_sigma = traits.Int(
        argstr='--smoothout=%d',
        desc='smooth transformed output with this sigma (default=0)',
    )
    verbose = traits.Bool(
        argstr='--verbose',
        desc='switch on diagnostic messages',
    )


class MSMOutputSpec(TraitedSpec):
    warped_mesh = File(
        desc='the warped input mesh (i.e., new vertex locations - this capture the warp field, '
        'much like a _warp.nii.gz file would for volumetric warps created by FNIRT).'
    )
    downsampled_warped_mesh = File(
        desc='a downsampled version of the warped_mesh where the resolution of this mesh will '
        'be equivalent to the resolution of the final datamesh'
    )
    warped_data = File(
        desc='the input data passed through the MSM warp and projected onto the target surface'
    )


class MSM(CommandLine):
    """
    MSM (Multimodal Surface Matching) is a tool for registering cortical surfaces.
    The tool has been developed and tested using FreeSurfer extracted surfaces.
    However, in principle the tool with work with any cortical surface extraction method provided
    the surfaces can be mapped to the sphere.
    The key advantage of the method is that alignment may be driven using a wide variety of
    univariate (sulcal depth, curvature, myelin), multivariate (Task fMRI, or Resting State
    Networks) or multimodal (combinations of folding, myelin and fMRI) feature sets.

    The main MSM tool is currently run from the command line using the program ``msm``.
    This enables fast alignment of spherical cortical surfaces by utilising a fast discrete
    optimisation framework (FastPD Komodakis 2007), which significantly reduces the search
    space of possible deformations for each vertex, and allows flexibility with regards to the
    choice of similarity metric used to match the images.

    >>> msm = MSM(
    ...   config_file=load('msm/MSMSulcStrainFinalconf'),
    ...   in_mesh='sub-01_hemi-L_sphere.surf.gii',
    ...   reference_mesh='tpl-fsaverage_hemi-L_den-164k_desc-std_sphere.surf.gii',
    ...   in_data='sub-01_hemi-L_sulc.shape.gii',
    ...   reference_data='tpl-fsaverage_hemi-L_den-164k_sulc.shape.gii',
    ...   out_base='L.',
    ... )
    >>> msm.cmdline  # doctest: +ELLIPSIS +NORMALIZE_WHITESPACE
    'msm --conf=.../MSMSulcStrainFinalconf \
    --indata=sub-01_hemi-L_sulc.shape.gii \
    --inmesh=sub-01_hemi-L_sphere.surf.gii \
    --out=L. \
    --refdata=tpl-fsaverage_hemi-L_den-164k_sulc.shape.gii \
    --refmesh=tpl-fsaverage_hemi-L_den-164k_desc-std_sphere.surf.gii'

    """

    input_spec = MSMInputSpec
    output_spec = MSMOutputSpec
    _cmd = 'msm'

    def _list_outputs(self):
        from nipype.utils.filemanip import split_filename

        outputs = self._outputs().get()
        out_base = self.inputs.out_base or split_filename(self.inputs.in_mesh)[1]
        cwd = Path.cwd()
        outputs['warped_mesh'] = str(cwd / (out_base + 'sphere.reg.surf.gii'))
        outputs['downsampled_warped_mesh'] = str(cwd / (out_base + 'sphere.LR.reg.surf.gii'))
        outputs['warped_data'] = str(cwd / (out_base + 'transformed_and_reprojected.func.gii'))
        return outputs

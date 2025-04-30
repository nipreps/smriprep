from nipype.interfaces.base import traits
from nipype.interfaces.fsl.preprocess import FAST as _FAST, FASTInputSpec


class _FixTraitFASTInputSpec(FASTInputSpec):
    bias_iters = traits.Range(
        low=0,
        high=10,
        argstr='-I %d',
        desc='number of main-loop iterations during bias-field removal',
    )


class FAST(_FAST):
    """
    A replacement for nipype.interfaces.fsl.preprocess.FAST that allows
    `bias_iters=0` to disable bias field correction entirely

    >>> from smriprep.interfaces.fsl import FixBiasItersFAST as FAST
    >>> fast = fsl.FAST()
    >>> fast.inputs.in_files = 'sub-01_desc-warped_T1w.nii.gz'
    >>> fast.cmdline
    'fast -o fast_ -S 1 -I 0 sub-01_desc-warped_T1w.nii.gz'
    """

    input_spec = _FixTraitFASTInputSpec


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
    """

    input_spec = _FixTraitFASTInputSpec


from nipype.interfaces.base import traits
from nipype.interfaces.fsl.preprocess import FAST, FASTInputSpec


class _FixTraitFASTInputSpec(FASTInputSpec):
    bias_iters = traits.Range(
        low=0,
        high=10,
        argstr='-I %d',
        desc='number of main-loop iterations during bias-field removal',
    )


class FixBiasItersFAST(FAST):
    """
    A replacement for nipype.interfaces.fsl.preprocess.FAST that allows
    `bias_iters=0` to disable bias field correction entirely
    """

    input_spec = _FixTraitFASTInputSpec

    def _run_interface(self, runtime, correct_return_codes=(0,)):
        # Run normally
        runtime = super()._run_interface(
            runtime, correct_return_codes
        )

        return runtime

"""Interfaces for manipulating GIFTI files."""
import os

import nibabel as nb
from nipype.interfaces.base import File, SimpleInterface, TraitedSpec, isdefined, traits


class MetricMathInputSpec(TraitedSpec):
    subject_id = traits.Str(desc='subject ID')
    hemisphere = traits.Enum(
        "L",
        "R",
        mandatory=True,
        desc='hemisphere',
    )
    metric = traits.Str(desc='name of metric to invert')
    metric_file = File(exists=True, mandatory=True, desc='input GIFTI file')
    operation = traits.Enum(
        "invert",
        "abs",
        "bin",
        mandatory=True,
        desc='operation to perform',
    )


class MetricMathOutputSpec(TraitedSpec):
    metric_file = File(desc='output GIFTI file')


class MetricMath(SimpleInterface):
    """Prepare GIFTI metric file for use in MSMSulc

    This interface mirrors the action of the following portion
    of FreeSurfer2CaretConvertAndRegisterNonlinear.sh::

        wb_command -set-structure ${metric_file} CORTEX_[LEFT|RIGHT]
        wb_command -metric-math "var * -1" ${metric_file} -var var ${metric_file}
        wb_command -set-map-names ${metric_file} -map 1 ${subject}_[L|R]_${metric}
        # If abs:
        wb_command -metric-math "abs(var)" ${metric_file} -var var ${metric_file}

    We do not add palette information to the output file.
    """

    input_spec = MetricMathInputSpec
    output_spec = MetricMathOutputSpec

    def _run_interface(self, runtime):
        subject, hemi, metric = self.inputs.subject_id, self.inputs.hemisphere, self.inputs.metric
        if not isdefined(subject):
            subject = 'sub-XYZ'

        img = nb.GiftiImage.from_filename(self.inputs.metric_file)
        # wb_command -set-structure
        img.meta["AnatomicalStructurePrimary"] = {'L': 'CortexLeft', 'R': 'CortexRight'}[hemi]
        darray = img.darrays[0]
        # wb_command -set-map-names
        meta = darray.meta
        meta['Name'] = f"{subject}_{hemi}_{metric}"

        datatype = darray.datatype
        if self.inputs.operation == "abs":
            # wb_command -metric-math "abs(var)"
            data = abs(darray.data)
        elif self.inputs.operation == "invert":
            # wb_command -metric-math "var * -1"
            data = -darray.data
        elif self.inputs.operation == "bin":
            # wb_command -metric-math "var > 0"
            data = darray.data > 0
            datatype = 'uint8'

        darray = nb.gifti.GiftiDataArray(
            data,
            intent=darray.intent,
            datatype=datatype,
            encoding=darray.encoding,
            endian=darray.endian,
            coordsys=darray.coordsys,
            ordering=darray.ind_ord,
            meta=meta,
        )
        img.darrays[0] = darray

        out_filename = os.path.join(runtime.cwd, f"{subject}.{hemi}.{metric}.native.shape.gii")
        img.to_filename(out_filename)
        self._results["metric_file"] = out_filename
        return runtime

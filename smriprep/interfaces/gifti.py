"""Interfaces for manipulating GIFTI files."""
import os

import nibabel as nb
from nipype.interfaces.base import File, SimpleInterface, TraitedSpec, isdefined, traits


class InvertShapeInputSpec(TraitedSpec):
    subject_id = traits.Str(desc='subject ID')
    hemisphere = traits.Enum(
        "L",
        "R",
        mandatory=True,
        desc='hemisphere',
    )
    shape = traits.Str(desc='name of shape to invert')
    shape_file = File(exists=True, mandatory=True, desc='input GIFTI file')


class InvertShapeOutputSpec(TraitedSpec):
    shape_file = File(desc='output GIFTI file')


class InvertShape(SimpleInterface):
    """Prepare GIFTI shape file for use in MSMSulc

    This interface mirrors the action of the following portion
    of FreeSurfer2CaretConvertAndRegisterNonlinear.sh::

        wb_command -set-structure ${shape_file} CORTEX_[LEFT|RIGHT]
        wb_command -metric-math "var * -1" ${shape_file} -var var ${shape_file}
        wb_command -set-map-names ${shape_file} -map 1 ${subject}_[L|R]_${shape}

    We do not add palette information to the output file.
    """

    input_spec = InvertShapeInputSpec
    output_spec = InvertShapeOutputSpec

    def _run_interface(self, runtime):
        subject, hemi, shape = self.inputs.subject_id, self.inputs.hemisphere, self.inputs.shape
        if not isdefined(subject):
            subject = 'sub-XYZ'

        img = nb.GiftiImage.from_filename(self.inputs.shape_file)
        # wb_command -set-structure
        img.meta["AnatomicalStructurePrimary"] = {'L': 'CortexLeft', 'R': 'CortexRight'}[hemi]
        darray = img.darrays[0]
        # wb_command -set-map-names
        meta = darray.meta
        meta['Name'] = f"{subject}_{hemi}_{shape}"

        # wb_command -metric-math "var * -1"
        inv = -darray.data

        darray = nb.gifti.GiftiDataArray(
            inv,
            intent=darray.intent,
            datatype=darray.datatype,
            encoding=darray.encoding,
            endian=darray.endian,
            coordsys=darray.coordsys,
            ordering=darray.ind_ord,
            meta=meta,
        )
        img.darrays[0] = darray

        out_filename = os.path.join(runtime.cwd, f"{subject}.{hemi}.{shape}.native.shape.gii")
        img.to_filename(out_filename)
        self._results["shape_file"] = out_filename
        return runtime

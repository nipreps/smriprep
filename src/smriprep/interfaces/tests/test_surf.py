import nibabel as nb
import numpy as np
from nipype.pipeline import engine as pe

from smriprep.interfaces.tests.data import load as load_test_data

from ..surf import MakeRibbon


def test_MakeRibbon(tmp_path):
    res_template = 'sub-fsaverage_res-4_hemi-{hemi}_desc-cropped_{surf}dist.nii.gz'
    white, pial = (
        [load_test_data(res_template.format(hemi=hemi, surf=surf)) for hemi in 'LR']
        for surf in ('wm', 'pial')
    )

    make_ribbon = pe.Node(
        MakeRibbon(white_distvols=white, pial_distvols=pial),
        name='make_ribbon',
        base_dir=tmp_path,
    )

    result = make_ribbon.run()

    ribbon = nb.load(result.outputs.ribbon)
    expected = nb.load(load_test_data('sub-fsaverage_res-4_desc-cropped_ribbon.nii.gz'))

    assert ribbon.shape == expected.shape
    assert np.allclose(ribbon.affine, expected.affine)
    assert np.array_equal(ribbon.dataobj, expected.dataobj)

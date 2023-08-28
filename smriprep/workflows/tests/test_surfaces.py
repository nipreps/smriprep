import os
from shutil import which

import nibabel as nb
import numpy as np
import pytest
from nipype.pipeline import engine as pe

from ..surfaces import init_anat_ribbon_wf, init_gifti_surfaces_wf
from ...data import load_resource


def test_ribbon_workflow(tmp_path):
    """Create ribbon mask for fsaverage subject"""

    for command in ("mris_convert", "wb_command", "fslmaths"):
        if not which(command):
            pytest.skip(f"Could not find {command} in PATH")

    if not os.path.exists(os.getenv('SUBJECTS_DIR')):
        pytest.skip("Could not find $SUBJECTS_DIR")

    # Low-res file that includes the fsaverage surfaces in its bounding box
    # We will use it both as a template and a comparison.
    test_ribbon = load_resource(
        "../interfaces/tests/data/sub-fsaverage_res-4_desc-cropped_ribbon.nii.gz"
    )

    gifti_surfaces_wf = init_gifti_surfaces_wf(surfaces=['white', 'pial'])
    anat_ribbon_wf = init_anat_ribbon_wf()
    anat_ribbon_wf.inputs.inputnode.t1w_mask = test_ribbon

    gifti_surfaces_wf.inputs.inputnode.subjects_dir = os.getenv('SUBJECTS_DIR')
    gifti_surfaces_wf.inputs.inputnode.subject_id = 'fsaverage'

    wf = pe.Workflow(name='test_ribbon_wf', base_dir=tmp_path)
    wf.connect(
        [
            (
                gifti_surfaces_wf,
                anat_ribbon_wf,
                [
                    ('outputnode.white', 'inputnode.white'),
                    ('outputnode.pial', 'inputnode.pial'),
                ],
            ),
        ]
    )
    result = wf.run()

    combine_ribbon_vol_hemis = next(
        node for node in result.nodes() if node.name == 'combine_ribbon_vol_hemis'
    )

    expected = nb.load(test_ribbon)
    ribbon = nb.load(combine_ribbon_vol_hemis.result.outputs.out_file)

    assert ribbon.shape == expected.shape
    assert np.allclose(ribbon.affine, expected.affine)
    # Mask data is binary, so we can use np.array_equal
    assert np.array_equal(ribbon.dataobj, expected.dataobj)

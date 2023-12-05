import os
from pathlib import Path
from shutil import which

import nibabel as nb
import numpy as np
import pytest
from nipype.pipeline import engine as pe

from ...data import load_resource
from ..surfaces import init_anat_ribbon_wf, init_gifti_surfaces_wf


def test_ribbon_workflow(tmp_path: Path):
    """Create ribbon mask for fsaverage subject"""

    for command in ('mris_convert', 'wb_command'):
        if not which(command):
            pytest.skip(f'Could not find {command} in PATH')

    if not os.path.exists(os.getenv('SUBJECTS_DIR')):
        pytest.skip('Could not find $SUBJECTS_DIR')

    # Low-res file that includes the fsaverage surfaces in its bounding box
    # We will use it both as a template and a comparison.
    test_ribbon = load_resource(
        '../interfaces/tests/data/sub-fsaverage_res-4_desc-cropped_ribbon.nii.gz'
    )

    gifti_surfaces_wf = init_gifti_surfaces_wf(surfaces=['white', 'pial'])
    anat_ribbon_wf = init_anat_ribbon_wf()
    anat_ribbon_wf.inputs.inputnode.ref_file = test_ribbon

    gifti_surfaces_wf.inputs.inputnode.subjects_dir = os.getenv('SUBJECTS_DIR')
    gifti_surfaces_wf.inputs.inputnode.subject_id = 'fsaverage'

    wf = pe.Workflow(name='test_ribbon_wf', base_dir=tmp_path)
    # fmt: off
    wf.connect([
        (gifti_surfaces_wf, anat_ribbon_wf, [
            ('outputnode.white', 'inputnode.white'),
            ('outputnode.pial', 'inputnode.pial'),
        ]),
    ])
    # fmt: on
    result = wf.run()

    make_ribbon = next(node for node in result.nodes() if node.name == 'make_ribbon')

    expected = nb.load(test_ribbon)
    ribbon = nb.load(make_ribbon.result.outputs.ribbon)

    assert ribbon.shape == expected.shape
    assert np.allclose(ribbon.affine, expected.affine)
    # Mask data is binary, so we can use np.array_equal
    assert np.array_equal(ribbon.dataobj, expected.dataobj)

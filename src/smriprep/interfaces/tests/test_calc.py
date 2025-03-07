import nibabel as nb
from nipype.pipeline import engine as pe
from templateflow import api as tf

from ..calc import T1T2Ratio


def test_T1T2Ratio(tmp_path):
    t1w = tf.get('MNI152NLin2009cAsym', desc=None, resolution=1, suffix='T1w')
    t2w = tf.get('MNI152NLin2009cAsym', desc=None, resolution=1, suffix='T2w')
    mask = tf.get('MNI152NLin2009cAsym', desc='brain', resolution=1, suffix='mask')

    t1t2 = pe.Node(
        T1T2Ratio(t1w_file=t1w, t2w_file=t2w, mask_file=mask),
        name='t1t2',
        base_dir=tmp_path,
    )

    result = t1t2.run()

    t1t2ratio = nb.load(result.outputs.t1t2_file)
    assert t1t2ratio.shape == (193, 229, 193)
    assert t1t2ratio.get_fdata().min() == 0.0
    assert t1t2ratio.get_fdata().max() == 100.0

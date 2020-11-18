from collections import namedtuple
from niworkflows.utils.spaces import SpatialReferences, Reference
from smriprep.workflows.base import init_single_subject_wf
BIDSLayout = namedtuple('BIDSLayout', ['root'])
wf = init_single_subject_wf(
    debug=False,
    freesurfer=True,
    fast_track=False,
    hires=True,
    layout=BIDSLayout('.'),
    longitudinal=False,
    low_mem=False,
    name='single_subject_wf',
    omp_nthreads=1,
    output_dir='.',
    skull_strip_fixed_seed=False,
    skull_strip_mode='force',
    skull_strip_template=Reference('OASIS30ANTs'),
    spaces=SpatialReferences(spaces=['MNI152NLin2009cAsym', 'fsaverage5']),
    subject_id='test',
    bids_filters=None,
)
from collections import namedtuple
from niworkflows.utils.spaces import SpatialReferences, Reference
from smriprep.workflows.base import init_single_subject_wf
BIDSLayout = namedtuple('BIDSLayout', ['root'])
spaces = SpatialReferences(spaces=['MNI152NLin2009cAsym', 'fsaverage5'])
spaces.checkpoint()
wf = init_single_subject_wf(
    sloppy=False,
    debug=False,
    freesurfer=True,
    derivatives=[],
    hires=True,
    fs_no_resume=False,
    layout=BIDSLayout('.'),
    longitudinal=False,
    low_mem=False,
    msm_sulc=False,
    name='single_subject_wf',
    omp_nthreads=1,
    output_dir='.',
    skull_strip_fixed_seed=False,
    skull_strip_mode='force',
    skull_strip_template=Reference('OASIS30ANTs'),
    spaces=spaces,
    subject_id='test',
    session_id=None,
    bids_filters=None,
    cifti_output=None,
)
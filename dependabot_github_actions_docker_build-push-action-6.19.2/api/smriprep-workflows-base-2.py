import os
from collections import namedtuple
BIDSLayout = namedtuple('BIDSLayout', ['root'])
os.environ['FREESURFER_HOME'] = os.getcwd()
from smriprep.workflows.base import init_smriprep_wf
from niworkflows.utils.spaces import SpatialReferences, Reference
spaces = SpatialReferences(spaces=['MNI152NLin2009cAsym', 'fsaverage5'])
spaces.checkpoint()
wf = init_smriprep_wf(
    sloppy=False,
    debug=False,
    derivatives=[],
    freesurfer=True,
    fs_subjects_dir=None,
    hires=True,
    fs_no_resume=False,
    layout=BIDSLayout('.'),
    longitudinal=False,
    low_mem=False,
    msm_sulc=False,
    omp_nthreads=1,
    output_dir='.',
    run_uuid='testrun',
    skull_strip_fixed_seed=False,
    skull_strip_mode='force',
    skull_strip_template=Reference('OASIS30ANTs'),
    spaces=spaces,
    subject_session_list=[('smripreptest', None)],
    work_dir='.',
    bids_filters=None,
    cifti_output=None,
)
from niworkflows.utils.spaces import SpatialReferences, Reference
from smriprep.workflows.anatomical import init_anat_fit_wf
wf = init_anat_fit_wf(
    bids_root='.',
    output_dir='.',
    freesurfer=True,
    hires=True,
    longitudinal=False,
    msm_sulc=True,
    t1w=['t1w.nii.gz'],
    t2w=['t2w.nii.gz'],
    flair=[],
    skull_strip_mode='force',
    skull_strip_template=Reference('OASIS30ANTs'),
    spaces=SpatialReferences(spaces=['MNI152NLin2009cAsym', 'fsaverage5']),
    precomputed={},
    debug=False,
    sloppy=False,
    omp_nthreads=1,
)
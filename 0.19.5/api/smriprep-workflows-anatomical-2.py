from niworkflows.utils.spaces import SpatialReferences, Reference
from smriprep.workflows.anatomical import init_anat_preproc_wf
spaces = SpatialReferences(spaces=['MNI152NLin2009cAsym', 'fsaverage5'])
spaces.checkpoint()
wf = init_anat_preproc_wf(
    bids_root='.',
    output_dir='.',
    freesurfer=True,
    hires=True,
    longitudinal=False,
    msm_sulc=False,
    t1w=['t1w.nii.gz'],
    t2w=[],
    skull_strip_mode='force',
    skull_strip_template=Reference('OASIS30ANTs'),
    spaces=spaces,
    precomputed={},
    omp_nthreads=1,
)
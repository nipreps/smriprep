from niworkflows.utils.spaces import SpatialReferences, Reference
from smriprep.workflows.anatomical import init_anat_preproc_wf
wf = init_anat_preproc_wf(
    bids_root='.',
    freesurfer=True,
    hires=True,
    longitudinal=False,
    t1w=['t1w.nii.gz'],
    omp_nthreads=1,
    output_dir='.',
    skull_strip_mode='force',
    skull_strip_template=Reference('OASIS30ANTs'),
    spaces=SpatialReferences(spaces=['MNI152NLin2009cAsym', 'fsaverage5']),
)
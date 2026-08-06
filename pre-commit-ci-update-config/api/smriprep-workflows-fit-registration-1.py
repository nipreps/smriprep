from smriprep.workflows.fit.registration import init_register_template_wf
wf = init_register_template_wf(
    sloppy=False,
    omp_nthreads=1,
    templates=['MNI152NLin2009cAsym', 'MNI152NLin6Asym'],
)
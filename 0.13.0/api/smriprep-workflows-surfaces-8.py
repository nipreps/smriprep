from smriprep.workflows.surfaces import init_resample_surfaces_wf
wf = init_resample_surfaces_wf(
    surfaces=['white', 'pial', 'midthickness'],
    grayord_density='91k',
)
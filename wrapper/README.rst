The *sMRIPrep* on Docker wrapper
--------------------------------
fMRIprep is a functional magnetic resonance image pre-processing pipeline
that is designed to provide an easily accessible, state-of-the-art interface
that is robust to differences in scan acquisition protocols and that requires
minimal user input, while providing easily interpretable and comprehensive
error and output reporting.

This is a lightweight Python wrapper to run *sMRIPrep*.
It generates the appropriate Docker commands, providing an intuitive interface
to running the *sMRIPrep* workflow in a Docker environment.
Docker must be installed and running. This can be checked
running ::

  docker info

Please acknowledge this work using the citation boilerplate that *sMRIPrep* includes
in the visual report generated for every subject processed.
For a more detailed description of the citation boilerplate and its relevance,
please check out the
`NiPreps documentation <https://www.nipreps.org/intro/transparency/#citation-boilerplates>`__.
Please report any feedback to our `GitHub repository <https://github.com/nipreps/fmriprep>`__.

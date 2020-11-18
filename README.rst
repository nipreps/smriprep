sMRIPrep: Structural MRI PREProcessing pipeline
===============================================

.. image:: https://img.shields.io/badge/docker-nipreps/smriprep-brightgreen.svg?logo=docker&style=flat
  :target: https://hub.docker.com/r/nipreps/smriprep/tags/
  :alt: Docker image available!

.. image:: https://circleci.com/gh/nipreps/smriprep/tree/master.svg?style=shield
  :target: https://circleci.com/gh/nipreps/smriprep/tree/master
  
.. image:: https://codecov.io/gh/nipreps/smriprep/branch/master/graph/badge.svg
  :target: https://codecov.io/gh/nipreps/smriprep
  :alt: Coverage report

.. image:: https://img.shields.io/pypi/v/smriprep.svg
  :target: https://pypi.python.org/pypi/smriprep/
  :alt: Latest Version
  
.. image:: https://img.shields.io/badge/doi-10.1038%2Fs41592--018--0235--4-blue.svg
  :target: https://doi.org/10.1038/s41592-018-0235-4
  :alt: Published in Nature Methods


*sMRIPrep* is a structural magnetic resonance imaging (sMRI) data
preprocessing pipeline that is designed to provide an easily accessible,
state-of-the-art interface that is robust to variations in scan acquisition
protocols and that requires minimal user input, while providing easily
interpretable and comprehensive error and output reporting.
It performs basic processing steps (subject-wise averaging, B1 field correction,
spatial normalization, segmentation, skullstripping etc.) providing
outputs that can be easily connected to subsequent tools such as
`fMRIPrep <https://github.com/nipreps/fmriprep>`__ or
`dMRIPrep <https://github.com/nipreps/dmriprep>`__.

.. image:: https://github.com/oesteban/smriprep/raw/033a6b4a54ecbd9051c45df979619cda69847cd1/docs/_resources/workflow.png

The workflow is based on `Nipype <https://nipype.readthedocs.io>`__ and encompases
a combination of tools from well-known software packages, including
`FSL <https://fsl.fmrib.ox.ac.uk/fsl/fslwiki/>`__,
`ANTs <https://stnava.github.io/ANTs/>`__,
`FreeSurfer <https://surfer.nmr.mgh.harvard.edu/>`__,
and `AFNI <https://afni.nimh.nih.gov/>`__.

More information and documentation can be found at
https://www.nipreps.org/smriprep/.
Support is provided on `neurostars.org <https://neurostars.org/tags/smriprep>`_.

Principles
----------

*sMRIPrep* is built around three principles:

1. **Robustness** - The pipeline adapts the preprocessing steps depending on
   the input dataset and should provide results as good as possible
   independently of scanner make, scanning parameters or presence of additional
   correction scans (such as fieldmaps).
2. **Ease of use** - Thanks to dependence on the BIDS standard, manual
   parameter input is reduced to a minimum, allowing the pipeline to run in an
   automatic fashion.
3. **"Glass box"** philosophy - Automation should not mean that one should not
   visually inspect the results or understand the methods.
   Thus, *sMRIPrep* provides visual reports for each subject, detailing the
   accuracy of the most important processing steps.
   This, combined with the documentation, can help researchers to understand
   the process and decide which subjects should be kept for the group level
   analysis.


Acknowledgements
----------------

Please acknowledge this work by mentioning explicitly the name of this software
(sMRIPrep) and the version, along with a link to the `GitHub repository
<https://github.com/nipreps/smriprep>`__ or the Zenodo reference
(doi:`10.5281/zenodo.2650521 <https://doi.org/10.5281/zenodo.2650521>`__).

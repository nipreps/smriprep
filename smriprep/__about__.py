# -*- coding: utf-8 -*-
# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
"""
Base module variables
"""

from ._version import get_versions
__version__ = get_versions()['version']
del get_versions

__author__ = 'The Nipy community'
__copyright__ = 'Copyright 2018, Center for Reproducible Neuroscience, Stanford University'
__credits__ = ['Oscar Esteban', 'Chris Gorgolewski', 'Christopher J. Markiewicz',
               'Russell A. Poldrack']
__license__ = '3-clause BSD'
__maintainer__ = 'Oscar Esteban'
__email__ = 'code@oscaresteban.es'
__status__ = 'Prototype'
__url__ = 'https://github.com/poldracklab/smriprep'
__description__ = ("sMRIPrep (Structural MRI PREprocessing) pipeline")
__longdesc__ = """\
The workflow is based on `Nipype <https://nipype.readthedocs.io>`_ and encompases a large
set of tools from well-known neuroimaging packages, including
`FSL <https://fsl.fmrib.ox.ac.uk/fsl/fslwiki/>`_,
`ANTs <https://stnava.github.io/ANTs/>`_,
`FreeSurfer <https://surfer.nmr.mgh.harvard.edu/>`_,
`AFNI <https://afni.nimh.nih.gov/>`_,
and `Nilearn <https://nilearn.github.io/>`_.
This pipeline was designed to provide the best software implementation for each state of
preprocessing, and will be updated as newer and better neuroimaging software becomes
available.

[Support `neurostars.org <https://neurostars.org/tags/smriprep>`_]
"""

DOWNLOAD_URL = (
    'https://github.com/poldracklab/{name}/archive/{ver}.tar.gz'.format(
        name=__package__, ver=__version__))


SETUP_REQUIRES = [
    'setuptools>=27.0',
]

REQUIRES = [
    'indexed_gzip>=0.8.8',
    'lockfile',
    'matplotlib>=2.2.0',
    'nibabel>=2.2.1',
    'nipype>=1.1.6',
    'niworkflows<0.10.0a0,>=0.9.0a2',
    'numpy',
    'packaging',
    'pybids',
    'pyyaml',
    'templateflow<0.2.0a0,>=0.1.7',
]


LINKS_REQUIRES = [
]

TESTS_REQUIRES = [
    "mock",
    "codecov",
    "pytest",
]

EXTRA_REQUIRES = {
    'doc': [
        'sphinx>=1.5.3',
        'sphinx_rtd_theme',
        'sphinx-argparse',
        'pydotplus',
        'pydot>=1.2.3',
        'nbsphinx',
    ],
    'tests': TESTS_REQUIRES,
    'duecredit': ['duecredit'],
    'datalad': ['datalad'],
    'resmon': ['psutil>=5.4.0'],
}
EXTRA_REQUIRES['docs'] = EXTRA_REQUIRES['doc']

# Enable a handle to install all extra dependencies at once
EXTRA_REQUIRES['all'] = list(set([
    v for deps in EXTRA_REQUIRES.values() for v in deps]))

CLASSIFIERS = [
    'Development Status :: 3 - Alpha',
    'Intended Audience :: Science/Research',
    'Topic :: Scientific/Engineering :: Image Recognition',
    'License :: OSI Approved :: BSD License',
    'Programming Language :: Python :: 3.5',
    'Programming Language :: Python :: 3.6',
    'Programming Language :: Python :: 3.7',
]

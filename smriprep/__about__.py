# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
"""
Base module variables
"""

from ._version import get_versions
__version__ = get_versions()['version']
del get_versions

__copyright__ = 'Copyright 2019, Center for Reproducible Neuroscience, Stanford University'
__credits__ = ['Oscar Esteban', 'Chris Gorgolewski', 'Christopher J. Markiewicz',
               'Russell A. Poldrack']
__url__ = 'https://github.com/poldracklab/smriprep'

DOWNLOAD_URL = (
    'https://github.com/poldracklab/{name}/archive/{ver}.tar.gz'.format(
        name=__package__, ver=__version__))

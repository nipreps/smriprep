#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Author: oesteban
# @Date:   2015-11-19 16:44:27
""" smriprep setup script """


def main():
    """ Install entry-point """
    from pathlib import Path
    from inspect import getfile, currentframe
    from setuptools import setup, find_packages
    from smriprep.__about__ import (
        __package__,
        __version__,
        __author__,
        __email__,
        __maintainer__,
        __license__,
        __description__,
        __longdesc__,
        __url__,
        DOWNLOAD_URL,
        CLASSIFIERS,
        REQUIRES,
        SETUP_REQUIRES,
        LINKS_REQUIRES,
        TESTS_REQUIRES,
        EXTRA_REQUIRES,
    )

    pkg_data = {
        __package__: [
            'data/*.json',
            'data/*.nii.gz',
            'data/*.mat',
            'data/boilerplate.bib',
            'data/itkIdentityTransform.txt',
            'data/reports/config.json',
            'data/reports/report.tpl',
        ]
    }

    version = None
    cmdclass = {}

    root_dir = Path(getfile(currentframe())).resolve().parent
    verfile = root_dir / __package__ / 'VERSION'
    if verfile.is_file():
        version = verfile.read_text().splitlines()[0].strip()
        pkg_data[__package__].insert(0, 'VERSION')

    if version is None:
        import versioneer
        version = versioneer.get_version()
        cmdclass = versioneer.get_cmdclass()

    setup(
        name=__package__,
        version=__version__,
        description=__description__,
        long_description=__longdesc__,
        author=__author__,
        author_email=__email__,
        maintainer=__maintainer__,
        maintainer_email=__email__,
        url=__url__,
        license=__license__,
        classifiers=CLASSIFIERS,
        download_url=DOWNLOAD_URL,
        # Dependencies handling
        setup_requires=SETUP_REQUIRES,
        install_requires=REQUIRES,
        tests_require=TESTS_REQUIRES,
        extras_require=EXTRA_REQUIRES,
        dependency_links=LINKS_REQUIRES,
        package_data=pkg_data,
        entry_points={'console_scripts': [
            'smriprep=smriprep.cli.run:main',
        ]},
        packages=find_packages(exclude=("tests",)),
        zip_safe=False,
        cmdclass=cmdclass,
    )


if __name__ == '__main__':
    main()

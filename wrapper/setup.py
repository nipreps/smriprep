import sys

from setuptools import setup
from setuptools.command.build_py import build_py
from setuptools.command.sdist import sdist
from setuptools_scm import get_version

# Give setuptools a hint to complain if it's too old a version
# 30.3.0 allows us to put most metadata in setup.cfg
# Should match pyproject.toml
# Not going to help us much without numpy or new pip, but gives us a shot
SETUP_REQUIRES = ['setuptools >= 30.3.0']
# This enables setuptools to install wheel on-the-fly
SETUP_REQUIRES += ['wheel'] if 'bdist_wheel' in sys.argv else []


VERSION = get_version(root='..', relative_to=__file__)


def update_version(target_file, version):
    with open(target_file) as fp:
        contents = fp.read()
    updated = contents.replace('__version__ = "99.99.99"', '__version__ = "{%s}"' % version)
    with open(target_file, 'w') as fp:
        fp.write(updated)


class PatchVersionSdist(sdist):
    def make_release_tree(self, base_dir, files):
        super().make_release_tree(base_dir, files)
        target_file = base_dir + '/smriprep_docker.py'
        update_version(target_file, VERSION)


class PatchVersionBuild(build_py):
    def run(self):
        super().run()
        target_file = self.build_lib + '/smriprep_docker.py'
        update_version(target_file, VERSION)


if __name__ == '__main__':
    setup(
        name='smriprep-docker',
        version=VERSION,
        setup_requires=SETUP_REQUIRES,
        cmdclass={
            'build_py': PatchVersionBuild,
            'sdist': PatchVersionSdist,
        },
    )

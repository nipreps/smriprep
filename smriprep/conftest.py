import os

import pytest
import numpy

from smriprep.data import load_resource

os.environ['NO_ET'] = '1'


@pytest.fixture(autouse=True)
def populate_namespace(doctest_namespace, tmp_path):
    doctest_namespace['os'] = os
    doctest_namespace['np'] = numpy
    doctest_namespace['load'] = load_resource
    doctest_namespace['testdir'] = tmp_path

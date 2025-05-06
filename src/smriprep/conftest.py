import os

import numpy as np
import pytest

from smriprep.data import load

os.environ['NO_ET'] = '1'


@pytest.fixture(autouse=True)
def _populate_namespace(doctest_namespace, tmp_path):
    doctest_namespace['os'] = os
    doctest_namespace['np'] = np
    doctest_namespace['load'] = load
    doctest_namespace['testdir'] = tmp_path

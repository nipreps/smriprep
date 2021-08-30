#!/bin/bash

echo Running tests

source tools/ci/activate.sh

set -eu

# Required variables
echo CHECK_TYPE = $CHECK_TYPE

set -x

if [ "${CHECK_TYPE}" == "test" ]; then
    pytest --doctest-modules --cov smriprep --cov-report xml \
        --junitxml=test-results.xml -v smriprep
else
    false
fi

set +eux

echo Done running tests

#!/bin/bash
docker run --rm -it \
    -v /tmp/data:/tmp/data:rw \
    -v /tmp/fslicense:/tmp/fslicense:ro \
    -v /tmp/templateflow:/home/smriprep/.cache/templateflow \
    -v /tmp/src/smriprep/docker/multiproc.coveragerc:/tmp/multiproc.coveragerc:ro \
    -v /tmp/src/smriprep/.circleci/nipype.cfg:/home/smriprep/.nipype/nipype.cfg \
    -e FS_LICENSE=/tmp/fslicense/license.txt \
    --entrypoint=pytest \
    nipreps/smriprep:latest \
    -v --doctest-modules --pyargs smriprep \
    --cov smriprep --cov-report=xml:/tmp/data/pytest_cov.xml \
    ${@:1}

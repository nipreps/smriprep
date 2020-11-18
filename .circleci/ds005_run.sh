#!/bin/bash
docker run -it -e FMRIPREP_DEV=1 -u $(id -u) \
    -v /tmp/data:/tmp/data:ro \
    -v /tmp/fslicense:/tmp/fslicense:ro \
    -v /tmp/ds005:/tmp/ds005 \
    -v /tmp/templateflow:/home/smriprep/.cache/templateflow \
    -v /tmp/src/smriprep/.circleci/nipype.cfg:/home/smriprep/.nipype/nipype.cfg \
    -e FMRIPREP_DEV=1 -u $(id -u) \
    -e COVERAGE_FILE=/tmp/ds005/work/.coverage \
    -e COVERAGE_RCFILE=/src/smriprep/docker/multiproc.coveragerc \
    --entrypoint=coverage \
    nipreps/smriprep:latest \
    run -m smriprep \
    /tmp/data/ds005 /tmp/ds005/derivatives participant \
    -w /tmp/ds005/work \
    --skull-strip-template MNI152NLin2009cAsym:res-2 \
    --sloppy --mem-gb 4 \
    --ncpus 2 --omp-nthreads 2 -vv \
    --fs-license-file /tmp/fslicense/license.txt \
    --fs-subjects-dir /tmp/ds005/freesurfer \
    ${@:1}

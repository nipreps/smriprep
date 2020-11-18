#!/bin/bash
docker run --rm -it -e FMRIPREP_DEV=1 -u $(id -u) \
    -v /tmp/data:/tmp/data:ro \
    -v /tmp/fslicense:/tmp/fslicense:ro \
    -v /tmp/ds054:/tmp/ds054 \
    -v /tmp/templateflow:/home/smriprep/.cache/templateflow \
    -v /tmp/src/smriprep/.circleci/nipype.cfg:/home/smriprep/.nipype/nipype.cfg \
    -e FMRIPREP_DEV=1 -u $(id -u) \
    -e COVERAGE_FILE=/tmp/ds054/work/.coverage \
    -e COVERAGE_RCFILE=/src/smriprep/docker/multiproc.coveragerc \
    --entrypoint=coverage \
    nipreps/smriprep:latest \
    run -m smriprep \
    /tmp/data/ds054 /tmp/ds054/derivatives participant \
    -w /tmp/ds054/work --fs-no-reconall --sloppy \
    --skull-strip-template OASIS30ANTs:res-1 \
    --output-spaces MNI152Lin MNI152NLin2009cAsym:res-2:res-native \
    --mem-gb 4 --ncpus 2 --omp-nthreads 2 -vv \
    --fs-license-file /tmp/fslicense/license.txt \
    ${@:1}

# sMRIPrep Docker Container Image distribution
#
# MIT License
#
# Copyright (c) The NiPreps Developers
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

ARG BASE_IMAGE=ghcr.io/nipreps/smriprep-base:20251104

#
# Build pixi environment
# The Pixi environment includes:
#   - Python
#     - Scientific Python stack (via conda-forge)
#     - General Python dependencies (via PyPI)
#   - NodeJS
#     - bids-validator
#     - svgo
#   - FSL (via fslconda)
#   - ants (via conda-forge)
#   - connectome-workbench (via conda-forge)
#   - ...
#
FROM ghcr.io/prefix-dev/pixi:0.77.1 AS build
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
                    ca-certificates \
                    git && \
    apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Run post-link scripts during install, but use global to keep out of source tree
RUN pixi config set --global run-post-link-scripts insecure

# Install dependencies before the package itself to leverage caching
RUN mkdir /app
COPY pixi.lock pyproject.toml /app
WORKDIR /app
RUN --mount=type=cache,target=/root/.cache/rattler pixi install -e smriprep -e test --frozen --skip smriprep
RUN --mount=type=cache,target=/root/.npm pixi run --as-is -e smriprep npm install -g svgo@^3.2.0 bids-validator@1.14.10
# Note that PATH gets hard-coded. Remove it and re-apply in final image
RUN pixi shell-hook -e smriprep --as-is | grep -v PATH > /shell-hook.sh
RUN pixi shell-hook -e test --as-is | grep -v PATH > /test-shell-hook.sh

# Finally, install the package
COPY . /app
RUN --mount=type=cache,target=/root/.cache/rattler pixi install -e smriprep -e test --frozen

#
# Pre-fetch templates
#
FROM ghcr.io/astral-sh/uv:python3.12-alpine AS templates
ENV TEMPLATEFLOW_HOME="/templateflow"
RUN uv pip install --system templateflow
COPY scripts/fetch_templates.py fetch_templates.py
RUN python fetch_templates.py


#
# Main stage
#
FROM ${BASE_IMAGE} AS base

# Create a shared $HOME directory
RUN useradd -m -s /bin/bash -G users smriprep
WORKDIR /home/smriprep
ENV HOME="/home/smriprep"

COPY --link --from=templates /templateflow /home/smriprep/.cache/templateflow

RUN chmod -R go=u $HOME

# Unless otherwise specified each process should only use one thread - nipype
# will handle parallelization
ENV MKL_NUM_THREADS=1 \
    OMP_NUM_THREADS=1

WORKDIR /tmp

FROM base AS test

COPY --link --from=build /app/.pixi/envs/test /app/.pixi/envs/test
COPY --link --from=build /test-shell-hook.sh /shell-hook.sh
RUN cat /shell-hook.sh >> $HOME/.bashrc
ENV PATH="/app/.pixi/envs/test/bin:$PATH"

ENV FSLDIR="/app/.pixi/envs/test"

FROM base AS smriprep

# Keep synced with wrapper's PKG_PATH
COPY --link --from=build /app/.pixi/envs/smriprep /app/.pixi/envs/smriprep
COPY --link --from=build /shell-hook.sh /shell-hook.sh
RUN cat /shell-hook.sh >> $HOME/.bashrc
ENV PATH="/app/.pixi/envs/smriprep/bin:$PATH"

ENV FSLDIR="/app/.pixi/envs/smriprep"

# For detecting the container
ENV IS_DOCKER_8395080871=1

ENTRYPOINT ["/app/.pixi/envs/smriprep/bin/smriprep"]

ARG BUILD_DATE
ARG VCS_REF
ARG VERSION
LABEL org.label-schema.build-date=$BUILD_DATE \
      org.label-schema.name="sMRIPrep" \
      org.label-schema.description="sMRIPrep - robust sMRI preprocessing tool" \
      org.label-schema.url="https://www.nipreps.org/smriprep" \
      org.label-schema.vcs-ref=$VCS_REF \
      org.label-schema.vcs-url="https://github.com/nipreps/smriprep" \
      org.label-schema.version=$VERSION \
      org.label-schema.schema-version="1.0"

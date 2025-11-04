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
# Build wheel
#
FROM ghcr.io/astral-sh/uv:python3.13-alpine AS src
RUN apk add --no-cache git
COPY . /src
RUN uvx --from=build pyproject-build --installer=uv /src

#
# Download stages
#

# Utilities for downloading packages
FROM ubuntu:jammy-20240125 AS downloader
# Bump the date to current to refresh curl/certificates/etc
RUN echo "2023.07.20"
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
                    binutils \
                    bzip2 \
                    ca-certificates \
                    curl \
                    unzip && \
    apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Micromamba
FROM downloader AS micromamba

WORKDIR /
# Bump the date to current to force update micromamba
RUN echo "2024.03.08"
RUN curl -Ls https://micro.mamba.pm/api/micromamba/linux-64/latest | tar -xvj bin/micromamba

ENV MAMBA_ROOT_PREFIX="/opt/conda"
COPY env.yml /tmp/env.yml
COPY requirements.txt /tmp/requirements.txt
WORKDIR /tmp
RUN micromamba create -y -f /tmp/env.yml && \
    micromamba clean -y -a

# UV_USE_IO_URING for apparent race-condition (https://github.com/nodejs/node/issues/48444)
# Check if this is still necessary when updating the base image.
ENV PATH="/opt/conda/envs/smriprep/bin:$PATH" \
    UV_USE_IO_URING=0
RUN npm install -g svgo@^3.2.0 bids-validator@^1.14.0 && \
    rm -r ~/.npm

#
# Main stage
#
FROM ${BASE_IMAGE} AS smriprep

# Create a shared $HOME directory
RUN useradd -m -s /bin/bash -G users smriprep
WORKDIR /home/smriprep
ENV HOME="/home/smriprep"

COPY --from=micromamba /bin/micromamba /bin/micromamba
COPY --from=micromamba /opt/conda/envs/smriprep /opt/conda/envs/smriprep

ENV MAMBA_ROOT_PREFIX="/opt/conda"
RUN micromamba shell init -s bash && \
    echo "micromamba activate smriprep" >> $HOME/.bashrc
ENV PATH="/opt/conda/envs/smriprep/bin:$PATH"

# Precaching atlases
COPY scripts/fetch_templates.py fetch_templates.py
RUN python fetch_templates.py && \
    rm fetch_templates.py && \
    find $HOME/.cache/templateflow -type d -exec chmod go=u {} + && \
    find $HOME/.cache/templateflow -type f -exec chmod go=u {} +

# FSL environment
ENV FSLDIR="/opt/conda/envs/smriprep"

# Unless otherwise specified each process should only use one thread - nipype
# will handle parallelization
ENV MKL_NUM_THREADS=1 \
    OMP_NUM_THREADS=1

# Installing SMRIPREP
COPY --from=src /src/dist/*.whl .
RUN pip install --no-cache-dir $( ls *.whl )[telemetry,test]

RUN find $HOME -type d -exec chmod go=u {} + && \
    find $HOME -type f -exec chmod go=u {} + && \
    rm -rf $HOME/.npm $HOME/.conda $HOME/.empty

# For detecting the container
ENV IS_DOCKER_8395080871=1

RUN ldconfig
WORKDIR /tmp
ENTRYPOINT ["/opt/conda/envs/smriprep/bin/smriprep"]

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

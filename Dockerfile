# sMRIPrep Docker Container Image distribution
#
# MIT License
#
# Copyright (c) 2022 The NiPreps Developers
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

# Use Ubuntu 20.04 LTS
#FROM ubuntu:focal-20210416

# Use pytorch official docker image
FROM pytorch/pytorch:1.2-cuda10.0-cudnn7-runtime

ENV CUDA_VERSION=10.0.130 \ 
    CUDA_PKG_VERSION=10-0=10.0.130-1 \
    NCCL_VERSION=2.4.8 \
    CUDNN_VERSION=7.6.5.32 \
    PYTHON_VERSION=3.6 \
    DEBIAN_FRONTEND="noninteractive" \
    LANG="C.UTF-8" \
    LC_ALL="C.UTF-8"

# Prepare environment
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
                    apt-utils \
                    autoconf \
                    build-essential \
                    bzip2 \
                    ca-certificates \
                    curl \
                    git \
                    libtool \
                    wget \
                    lsb-release \
                    netbase \
                    pkg-config \
                    unzip \
                    cmake \
                    gawk \
                    perl-modules \                     
                    tcsh \
                    time \
                    bzip2 \
                    libx11-6 \
                    libjpeg-dev \
                    bc \
                    libgomp1 \
                    libglu1-mesa \
                    libglu1-mesa-dev \
                    xvfb && \
    rm -rf /var/lib/apt/lists/*


# Installing freesurfer
COPY docker/files/freesurfer7.2-exclude.txt /usr/local/etc/freesurfer7.2-exclude.txt
RUN curl -sSL https://surfer.nmr.mgh.harvard.edu/pub/dist/freesurfer/7.2.0/freesurfer-linux-ubuntu18_amd64-7.2.0.tar.gz \
￼    | tar zxv --no-same-owner -C /opt --exclude-from=/usr/local/etc/freesurfer7.2-exclude.txt

# Install miniconda and needed python packages (for FastSurferCNN)
#RUN wget -qO ~/miniconda.sh https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh  && \
#     chmod +x ~/miniconda.sh && \
#     ~/miniconda.sh -b -p /opt/conda && \
#     rm ~/miniconda.sh && \
RUN  /opt/conda/bin/conda install python-dateutil pyyaml numpy scipy matplotlib h5py scikit-image && \
     /opt/conda/bin/conda install -y -c pytorch cudatoolkit=10.0 "pytorch=1.2.0=py3.6_cuda10.0.130_cudnn7.6.2_0" torchvision=0.4.0 && \
     /opt/conda/bin/conda install -c conda-forge scikit-sparse nibabel=2.5.1 pillow=8.3.2 && \
     /opt/conda/bin/conda clean -ya
ENV PATH /opt/conda/bin:$PATH

# install LaPy for FastSurfer
RUN python3.6 -m pip install -U git+https://github.com/Deep-MI/LaPy.git#egg=lapy

# Add FastSurfer (copy application code) to docker image
RUN cd /opt &&  git clone https://github.com/Deep-MI/FastSurfer.git
ENV FASTSURFER_HOME=/opt/FastSurfer


# Simulate SetUpFreeSurfer.sh
ENV FSL_DIR="/opt/fsl-6.0.5.1" \
    OS="Linux" \
    FS_OVERRIDE=0 \
    FIX_VERTEX_AREA="" \
    FSF_OUTPUT_FORMAT="nii.gz" \
    FREESURFER_HOME="/opt/freesurfer"
ENV SUBJECTS_DIR="$FREESURFER_HOME/subjects" \
    FUNCTIONALS_DIR="$FREESURFER_HOME/sessions" \
    MNI_DIR="$FREESURFER_HOME/mni" \
    LOCAL_DIR="$FREESURFER_HOME/local" \
    MINC_BIN_DIR="$FREESURFER_HOME/mni/bin" \
    MINC_LIB_DIR="$FREESURFER_HOME/mni/lib" \
    MNI_DATAPATH="$FREESURFER_HOME/mni/data"
ENV PERL5LIB="$MINC_LIB_DIR/perl5/5.8.5" \
    MNI_PERL5LIB="$MINC_LIB_DIR/perl5/5.8.5" \
    PATH="$FREESURFER_HOME/bin:$FREESURFER_HOME/tktools:$MINC_BIN_DIR:$PATH"

# FSL 6.0.5.1
RUN apt-get update -qq \
    && apt-get install -y -q --no-install-recommends \
           bc \
           dc \
           file \
           libfontconfig1 \
           libfreetype6 \
           libgl1-mesa-dev \
           libgl1-mesa-dri \
           libglu1-mesa-dev \
           libgomp1 \
           libice6 \
           libxcursor1 \
           libxft2 \
           libxinerama1 \
           libxrandr2 \
           libxrender1 \
           libxt6 \
           sudo \
           wget \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && echo "Downloading FSL ..." \
    && mkdir -p /opt/fsl-6.0.5.1 \
    && curl -fsSL --retry 5 https://fsl.fmrib.ox.ac.uk/fsldownloads/fsl-6.0.5.1-centos7_64.tar.gz \
    | tar -xz -C /opt/fsl-6.0.5.1 --strip-components 1 \
    --exclude "fsl/config" \
    --exclude "fsl/data/atlases" \
    --exclude "fsl/data/first" \
    --exclude "fsl/data/mist" \
    --exclude "fsl/data/possum" \
    --exclude "fsl/data/standard/bianca" \
    --exclude "fsl/data/standard/tissuepriors" \
    --exclude "fsl/doc" \
    --exclude "fsl/etc/default_flobs.flobs" \
    --exclude "fsl/etc/fslconf" \
    --exclude "fsl/etc/js" \
    --exclude "fsl/etc/luts" \
    --exclude "fsl/etc/matlab" \
    --exclude "fsl/extras" \
    --exclude "fsl/include" \
    --exclude "fsl/python" \
    --exclude "fsl/refdoc" \
    --exclude "fsl/src" \
    --exclude "fsl/tcl" \
    --exclude "fsl/bin/FSLeyes" \
    && find /opt/fsl-6.0.5.1/bin -type f -not \( \
        -name "applywarp" -or \
        -name "bet" -or \
        -name "bet2" -or \
        -name "convert_xfm" -or \
        -name "fast" -or \
        -name "flirt" -or \
        -name "fsl_regfilt" -or \
        -name "fslhd" -or \
        -name "fslinfo" -or \
        -name "fslmaths" -or \
        -name "fslmerge" -or \
        -name "fslroi" -or \
        -name "fslsplit" -or \
        -name "fslstats" -or \
        -name "imtest" -or \
        -name "mcflirt" -or \
        -name "melodic" -or \
        -name "prelude" -or \
        -name "remove_ext" -or \
        -name "susan" -or \
        -name "topup" -or \
        -name "zeropad" \) -delete \
    && find /opt/fsl-6.0.5.1/data/standard -type f -not -name "MNI152_T1_2mm_brain.nii.gz" -delete
ENV FSLDIR="/opt/fsl-6.0.5.1" \
    PATH="/opt/fsl-6.0.5.1/bin:$PATH" \
    FSLOUTPUTTYPE="NIFTI_GZ" \
    FSLMULTIFILEQUIT="TRUE" \
    FSLLOCKDIR="" \
    FSLMACHINELIST="" \
    FSLREMOTECALL="" \
    FSLGECUDAQ="cuda.q" \
    LD_LIBRARY_PATH="/opt/fsl-6.0.5.1/lib:$LD_LIBRARY_PATH"
# switch back to en-US utf-8
RUN apt-get update -qq && apt-get install locales && \
    sed -i '/en_US.UTF-8/s/^# //g' /etc/locale.gen && \
    locale-gen
ENV LANG="en_US.UTF-8" \
    LC_ALL="en_US.UTF-8" \
    LANGUAGE="en_US:en"
RUN ls /etc/ssl/certs/


# Convert3D (neurodocker build) - adapted to allow for local copy of Convert3D 
#    my build machine was giving ca-certificates errors for fetching C3D from sourceforge in build
#RUN echo "Downloading Convert3D ..." \
#    && mkdir -p /opt/convert3d-1.0.0 \
#    && cd /opt/ && curl -fsSL https://sourceforge.net/projects/c3d/files/c3d/1.0.0/c3d-1.0.0-Linux-x86_64.tar.gz \
COPY c3d-1.0.0-Linux-x86_64.tar.gz /opt/c3d-1.0.0-Linux-x86_64.tar.gz
RUN cd /opt/ && mkdir -p /opt/convert3d-1.0.0 && tar -xzf c3d-1.0.0-Linux-x86_64.tar.gz -C /opt/convert3d-1.0.0 --strip-components 1 \
    --exclude "c3d-1.0.0-Linux-x86_64/lib" \
    --exclude "c3d-1.0.0-Linux-x86_64/share" \
    --exclude "c3d-1.0.0-Linux-x86_64/bin/c3d_gui"
ENV C3DPATH="/opt/convert3d-1.0.0" \
    PATH="/opt/convert3d-1.0.0/bin:$PATH"

# AFNI latest (neurodocker build)
RUN apt-get update -qq \
    && apt-get install -y -q --no-install-recommends \
           apt-utils \
           ed \
           gsl-bin \
           libglib2.0-0 \
           libglu1-mesa-dev \
           libglw1-mesa \
           libgomp1 \
           libjpeg62 \
           libxm4 \
           netpbm \
           tcsh \
           xfonts-base \
           xvfb \
    && apt-get clean -y \
    && rm -rf /var/lib/apt/lists/* \
    && curl -sSL --retry 5 -o /tmp/multiarch.deb http://archive.ubuntu.com/ubuntu/pool/main/g/glibc/multiarch-support_2.27-3ubuntu1.5_amd64.deb \
    && dpkg -i /tmp/multiarch.deb \
    && rm /tmp/multiarch.deb \
    && curl -sSL --retry 5 -o /tmp/libxp6.deb http://mirrors.kernel.org/debian/pool/main/libx/libxp/libxp6_1.0.2-2_amd64.deb \
    && dpkg -i /tmp/libxp6.deb \
    && rm /tmp/libxp6.deb \
    && curl -sSL --retry 5 -o /tmp/libpng.deb http://snapshot.debian.org/archive/debian-security/20160113T213056Z/pool/updates/main/libp/libpng/libpng12-0_1.2.49-1%2Bdeb7u2_amd64.deb \
    && dpkg -i /tmp/libpng.deb \
    && rm /tmp/libpng.deb \
    && apt-get install -f -y \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && gsl2_path="$(find / -name 'libgsl.so.19' || printf '')" \
    && if [ -n "$gsl2_path" ]; then \
         ln -sfv "$gsl2_path" "$(dirname $gsl2_path)/libgsl.so.0"; \
    fi \
    && ldconfig \
    && echo "Downloading AFNI ..." \
    && mkdir -p /opt/afni-latest \
    && curl -fsSL --retry 5 https://afni.nimh.nih.gov/pub/dist/tgz/linux_openmp_64.tgz \
    | tar -xz -C /opt/afni-latest --strip-components 1 \
    --exclude "linux_openmp_64/*.gz" \
    --exclude "linux_openmp_64/funstuff" \
    --exclude "linux_openmp_64/shiny" \
    --exclude "linux_openmp_64/afnipy" \
    --exclude "linux_openmp_64/lib/RetroTS" \
    --exclude "linux_openmp_64/meica.libs" \
    # Keep only what we use
    && find /opt/afni-latest -type f -not \( \
        -name "3dTshift" -or \
        -name "3dUnifize" -or \
        -name "3dAutomask" -or \
        -name "3dvolreg" \) -delete

ENV PATH="/opt/afni-latest:$PATH" \
    AFNI_IMSAVE_WARNINGS="NO" \
    AFNI_PLUGINPATH="/opt/afni-latest"

# Installing ANTs 2.3.3 (NeuroDocker build)
# Note: the URL says 2.3.4 but it is actually 2.3.3
ENV ANTSPATH="/opt/ants" \
    PATH="/opt/ants:$PATH"
WORKDIR $ANTSPATH
RUN curl -sSL "https://dl.dropbox.com/s/gwf51ykkk5bifyj/ants-Linux-centos6_x86_64-v2.3.4.tar.gz" \
    | tar -xzC $ANTSPATH --strip-components 1

# nipreps/miniconda:py39_0525.0
COPY --from=nipreps/miniconda@sha256:40fffd37963502dcd8549773559fc21182f52460e59e0ad6398a84faf6055641 /opt/conda /opt/conda

RUN ln -s /opt/conda/etc/profile.d/conda.sh /etc/profile.d/conda.sh && \
    echo ". /opt/conda/etc/profile.d/conda.sh" >> ~/.bashrc && \
    echo "conda activate base" >> ~/.bashrc

# Set CPATH for packages relying on compiled libs (e.g. indexed_gzip)
ENV PATH="/opt/conda/bin:$PATH" \
    CPATH="/opt/conda/include:$CPATH" \
    LD_LIBRARY_PATH="/opt/conda/lib:$LD_LIBRARY_PATH" \
    LANG="C.UTF-8" \
    LC_ALL="C.UTF-8" \
    PYTHONNOUSERSITE=1

# Unless otherwise specified each process should only use one thread - nipype
# will handle parallelization
ENV MKL_NUM_THREADS=1 \
    OMP_NUM_THREADS=1

# Create a shared $HOME directory
RUN useradd -m -s /bin/bash -G users smriprep
WORKDIR /home/smriprep
ENV HOME="/home/smriprep" \
    LD_LIBRARY_PATH="/usr/lib/x86_64-linux-gnu:$LD_LIBRARY_PATH"

RUN echo ". /opt/conda/etc/profile.d/conda.sh" >> $HOME/.bashrc && \
    echo "conda activate base" >> $HOME/.bashrc

# Precaching atlases
COPY scripts/fetch_templates.py fetch_templates.py

RUN /opt/conda/bin/python fetch_templates.py && \
    rm fetch_templates.py && \
    find $HOME/.cache/templateflow -type d -exec chmod go=u {} + && \
    find $HOME/.cache/templateflow -type f -exec chmod go=u {} +

# Installing sMRIPREP
COPY . /src/smriprep
ARG VERSION
# Force static versioning within container
RUN echo "${VERSION}" > /src/smriprep/smriprep/VERSION && \
    echo "include smriprep/VERSION" >> /src/smriprep/MANIFEST.in && \
    /opt/conda/bin/python -m pip install --no-cache-dir "/src/smriprep[all]"

RUN find $HOME -type d -exec chmod go=u {} + && \
    find $HOME -type f -exec chmod go=u {} + && \
    rm -rf $HOME/.npm $HOME/.conda $HOME/.empty

# HACK for FreeSurfer 7.2.0
# Fixed in https://github.com/freesurfer/freesurfer/pull/886, so remove on release
ENV FREESURFER="/opt/freesurfer"

ENV IS_DOCKER_8395080871=1

RUN ldconfig
WORKDIR /tmp
ENTRYPOINT ["/opt/conda/bin/smriprep"]

ARG BUILD_DATE
ARG VCS_REF
ARG VERSION
LABEL org.label-schema.build-date=$BUILD_DATE \
      org.label-schema.name="sMRIPrep" \
      org.label-schema.description="sMRIPrep - robust structural MRI preprocessing tool" \
      org.label-schema.url="http://smriprep.org" \
      org.label-schema.vcs-ref=$VCS_REF \
      org.label-schema.vcs-url="https://github.com/nipreps/smriprep" \
      org.label-schema.version=$VERSION \
      org.label-schema.schema-version="1.0"

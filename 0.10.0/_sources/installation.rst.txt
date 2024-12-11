.. include:: links.rst

------------
Installation
------------

There are two ways of getting *sMRIPrep* installed:

* within a `Manually Prepared Environment (Python 3.5+)`_, also known as
  *bare-metal installation*; or
* using container technologies (RECOMMENDED), such as
  `Docker <https://fmriprep.readthedocs.io/en/stable/docker.html>`__ or
  `Singularity <https://fmriprep.readthedocs.io/en/stable/singularity.html>`__.

Once you have your *bare-metal* environment set-up (first option above),
the next step is executing the ``smriprep`` command-line.
The ``smriprep`` command-line options are documented in the :ref:`usage`
section.
The ``smriprep`` command-line adheres to the `BIDS-Apps recommendations
for the user interface <usage.html#execution-and-the-bids-format>`__.
Therefore, the command-line has the following structure:
::

  $ smriprep <input_bids_path> <derivatives_path> <analysis_level> <named_options>

On the other hand, if you chose a container infrastructure, then
the command-line will be composed of a preamble to configure the
container execution followed by the ``smriprep`` command-line options
as if you were running it on a *bare-metal* installation.
The command-line structure above is then modified as follows:
::

  $ <container_command_and_options> <container_image> \
       <input_bids_path> <derivatives_path> <analysis_level> <smriprep_named_options>

Therefore, once specified, the container options and the image to be run
the command line is the same as for the *bare-metal* installation but dropping
the ``smriprep`` executable name.

Container technologies: Docker and Singularity
==============================================
Container technologies are operating-system-level virtualization methods to run Linux systems
using the host's Linux kernel.
This is a lightweight approach to virtualization, as compares to virtual machines.


.. _installation_docker:

Docker (recommended for PC/laptop and commercial Cloud)
-------------------------------------------------------
Probably, the most popular framework to execute containers is Docker.
If you are to run *sMRIPrep* on your PC/laptop, this is the RECOMMENDED way of execution.
Please make sure you follow the `Docker installation`_ instructions.
You can check your `Docker Engine`_ installation running their ``hello-world`` image: ::

    $ docker run --rm hello-world

If you have a functional installation, then you should obtain the following output. ::
    
    Hello from Docker!
    This message shows that your installation appears to be working correctly.
    
    To generate this message, Docker took the following steps:
     1. The Docker client contacted the Docker daemon.
     1. The Docker daemon pulled the "hello-world" image from the Docker Hub.
        (amd64)
     1. The Docker daemon created a new container from that image which runs the
        executable that produces the output you are currently reading.
     1. The Docker daemon streamed that output to the Docker client, which sent it
        to your terminal.
    
    To try something more ambitious, you can run an Ubuntu container with:
     $ docker run -it ubuntu bash
    
    Share images, automate workflows, and more with a free Docker ID:
     https://hub.docker.com/
    
    For more examples and ideas, visit:
     https://docs.docker.com/get-started/

After checking your Docker Engine is capable of running Docker images, then go ahead
and `check out our documentation <https://fmriprep.readthedocs.io/en/stable/docker.html>`__
to run the *sMRIPrep* image.
The list of Docker images ready to use is found at the `Docker Hub`_, 
under the ``nipreps/smriprep`` identifier.

The ``smriprep-docker`` wrapper
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
This is the easiest way to `run sMRIPrep using Docker
<https://fmriprep.readthedocs.io/en/stable/docker.html#running-smriprep-with-the-smriprep-docker-wrapper>`__.
The `Docker wrapper`_ is a Python script that operates the Docker Engine seamlessly
as if you were running ``smriprep`` directly.
To that end, ``smriprep-docker`` reinterprets the command-line you are passing and
converts it into a ``docker run`` command.
The wrapper just requires Python and an Internet connection.
Install the wrapper using a Python distribution system, e.g.::

    $ python -m pip install --user --upgrade smriprep-docker

Singularity (recommended for HPC)
---------------------------------

For security reasons, many :abbr:`HPCs (High-Performance Computing)` (e.g., TACC_)
do not allow Docker containers, but do allow Singularity_ containers.
The improved security for multi-tenant systems comes at the price of some limitations
and extra steps necessary for execution.
Please make sure you `follow our tips and tricks to run sMRIPrep's Singularity images
<singularity.html>`_.


Manually Prepared Environment (Python 3.5+)
===========================================

.. warning::

   This method is not recommended! Please checkout container alternatives
   such as `Docker <https://fmriprep.readthedocs.io/en/stable/docker.html>`__, or
   `Singularity <https://fmriprep.readthedocs.io/en/stable/singularity.html>`__.

Make sure all of *sMRIPrep*'s `External Dependencies`_ are installed.
These tools must be installed and their binaries available in the
system's ``$PATH``.
A relatively interpretable description of how your environment can be set-up
is found in the `Dockerfile <https://github.com/nipreps/smriprep/blob/master/Dockerfile>`_.
As an additional installation setting, FreeSurfer requires a license file (see :ref:`fs_license`).

On a functional Python 3.5 (or above) environment with ``pip`` installed,
*sMRIPrep* can be installed using the habitual command ::

    $ python -m pip install smriprep

Check your installation with the ``--version`` argument ::

    $ smriprep --version


External Dependencies
---------------------

*sMRIPrep* is written using Python 3.5 (or above), and is based on
nipype_.

*sMRIPrep* requires some other neuroimaging software tools that are
not handled by the Python's packaging system (Pypi) used to deploy
the ``smriprep`` package:

- FSL_ (version 5.0.9)
- ANTs_ (version 2.2.0 - NeuroDocker build)
- AFNI_ (version Debian-16.2.07)
- `C3D <https://sourceforge.net/projects/c3d/>`_ (version 1.0.0)
- FreeSurfer_ (version 6.0.1)
- `bids-validator <https://github.com/bids-standard/bids-validator>`_ (version 1.1.0)

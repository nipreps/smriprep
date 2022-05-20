# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
#
# Copyright 2021 The NiPreps Developers <nipreps@gmail.com>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# We support and encourage derived works from this project, please read
# about our expectations at
#
#     https://www.nipreps.org/community/licensing/
#
"""Nipype's recon-all replacement."""
import os
from nipype import logging
from nipype.utils.filemanip import check_depends
from nipype.interfaces.base import traits, InputMultiObject, isdefined
from nipype.interfaces import freesurfer as fs

iflogger = logging.getLogger("nipype.interface")


class _ReconAllInputSpec(fs.preprocess.ReconAllInputSpec):
    directive = traits.Enum(
        "all",
        "autorecon1",
        # autorecon2 variants
        "autorecon2",
        "autorecon2-volonly",
        "autorecon2-perhemi",
        "autorecon2-inflate1",
        "autorecon2-cp",
        "autorecon2-wm",
        # autorecon3 variants
        "autorecon3",
        "autorecon3-T2pial",
        # Mix of autorecon2 and autorecon3 steps
        "autorecon-pial",
        "autorecon-hemi",
        # Not "multi-stage flags"
        "localGI",
        "qcache",
        argstr="-%s",
        desc="process directive",
        usedefault=True,
        xor=["steps"],
        position=0,
    )
    steps = InputMultiObject(
        traits.Enum(
            # autorecon1
            "motioncor",
            "talairach",
            "nuintensitycor",
            "normalization",
            "skullstrip",
            # autorecon2-volonly
            "gcareg",
            "canorm",
            "careg",
            "careginv",  # 5.3
            "rmneck",  # 5.3
            "skull-lta",  # 5.3
            "calabel",
            "normalization2",
            "maskbfs",
            "segmentation",
            # autorecon2 per-hemi
            "tessellate",
            "smooth1",
            "inflate1",
            "qsphere",
            "fix",
            "white",
            "smooth2",
            "inflate2",
            "curvHK",  # 6.0
            "curvstats",
            # autorecon3 per-hemi
            "sphere",
            "surfreg",
            "jacobian_white",
            "avgcurv",
            "cortparc",
            "pial",
            "pctsurfcon",
            "parcstats",
            "cortparc2",
            "parcstats2",
            "cortparc3",
            "parcstats3",
            "label-exvivo-ec",
            # autorecon vol
            "cortribbon",
            "hyporelabel",  # 6.0
            "segstats",
            "aparc2aseg",
            "apas2aseg",  # 6.0
            "wmparc",
            "balabels",
        ),
        desc="specific process directives",
        xor=["directive"],
        position=0,
    )
    hemi = traits.Enum("lh", "rh", desc="hemisphere to process", argstr="-%s-only")


class ReconAll(fs.ReconAll):
    input_spec = _ReconAllInputSpec

    @property
    def cmdline(self):
        cmd = super(fs.ReconAll, self).cmdline

        # Adds '-expert' flag if expert flags are passed
        # Mutually exclusive with 'expert' input parameter
        cmd += self._prep_expert_file()

        if not self._is_resuming():
            return cmd
        subjects_dir = self.inputs.subjects_dir
        if not isdefined(subjects_dir):
            subjects_dir = self._gen_subjects_dir()

        # Check only relevant steps
        directive = self.inputs.directive
        if not isdefined(directive):
            steps = []
            if isdefined(self.inputs.steps):
                steps = [step for step in self._steps if step[0] in self.inputs.steps]
        elif directive == "autorecon1":
            steps = self._autorecon1_steps
        elif directive == "autorecon2-volonly":
            steps = self._autorecon2_volonly_steps
        elif directive == "autorecon2-perhemi":
            steps = self._autorecon2_perhemi_steps
        elif directive.startswith("autorecon2"):
            if isdefined(self.inputs.hemi):
                if self.inputs.hemi == "lh":
                    steps = self._autorecon2_volonly_steps + self._autorecon2_lh_steps
                else:
                    steps = self._autorecon2_volonly_steps + self._autorecon2_rh_steps
            else:
                steps = self._autorecon2_steps
        elif directive == "autorecon-hemi":
            if self.inputs.hemi == "lh":
                steps = self._autorecon_lh_steps
            else:
                steps = self._autorecon_rh_steps
        elif directive == "autorecon3":
            steps = self._autorecon3_steps
        else:
            steps = self._steps

        no_run = True
        flags = []
        for step, outfiles, infiles in steps:
            flag = "-{}".format(step)
            noflag = "-no{}".format(step)
            if noflag in cmd:
                continue
            elif flag in cmd:
                no_run = False
                continue

            subj_dir = os.path.join(subjects_dir, self.inputs.subject_id)
            if check_depends(
                [os.path.join(subj_dir, f) for f in outfiles],
                [os.path.join(subj_dir, f) for f in infiles],
            ):
                flags.append(noflag)
            else:
                if isdefined(self.inputs.steps):
                    flags.append(flag)
                no_run = False

        if no_run and not self.force_run:
            iflogger.info("recon-all complete : Not running")
            return "echo recon-all: nothing to do"

        cmd += " " + " ".join(flags)
        iflogger.info("resume recon-all : %s", cmd)
        return cmd

    def _format_arg(self, name, trait_spec, value):
        # Nipype disables this if -autorecon-hemi is passed
        # We need to use it either way to prevent undesired behavior
        if name == "hemi":
            return trait_spec.argstr % value
        return super()._format_arg(name, trait_spec, value)

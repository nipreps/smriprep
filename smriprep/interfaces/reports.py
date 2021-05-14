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
"""Interfaces to generate reportlets."""

from pathlib import Path
import time

from nipype.interfaces.base import (
    TraitedSpec,
    BaseInterfaceInputSpec,
    File,
    Directory,
    InputMultiObject,
    Str,
    isdefined,
    SimpleInterface,
)
from nipype.interfaces import freesurfer as fs
from nipype.interfaces.io import FSSourceInputSpec as _FSSourceInputSpec
from nipype.interfaces.mixins import reporting

from niworkflows.interfaces.reportlets.base import _SVGReportCapableInputSpec


SUBJECT_TEMPLATE = """\
\t<ul class="elem-desc">
\t\t<li>Subject ID: {subject_id}</li>
\t\t<li>Structural images: {n_t1s:d} T1-weighted {t2w}</li>
\t\t<li>Standard spaces: {output_spaces}</li>
\t\t<li>FreeSurfer reconstruction: {freesurfer_status}</li>
\t</ul>
"""

ABOUT_TEMPLATE = """\t<ul>
\t\t<li>sMRIPrep version: {version}</li>
\t\t<li>sMRIPrep command: <code>{command}</code></li>
\t\t<li>Date preprocessed: {date}</li>
\t</ul>
</div>
"""


class _SummaryOutputSpec(TraitedSpec):
    out_report = File(exists=True, desc="HTML segment containing summary")


class SummaryInterface(SimpleInterface):
    """Base Nipype interface for html summaries."""

    output_spec = _SummaryOutputSpec

    def _run_interface(self, runtime):
        segment = self._generate_segment()
        path = Path(runtime.cwd) / "report.html"
        path.write_text(segment)
        self._results["out_report"] = str(path)
        return runtime

    def _generate_segment(self):
        raise NotImplementedError


class _SubjectSummaryInputSpec(BaseInterfaceInputSpec):
    t1w = InputMultiObject(File(exists=True), desc="T1w structural images")
    t2w = InputMultiObject(File(exists=True), desc="T2w structural images")
    subjects_dir = Directory(desc="FreeSurfer subjects directory")
    subject_id = Str(desc="Subject ID")
    output_spaces = InputMultiObject(Str, desc="list of standard spaces")


class _SubjectSummaryOutputSpec(_SummaryOutputSpec):
    # This exists to ensure that the summary is run prior to the first ReconAll
    # call, allowing a determination whether there is a pre-existing directory
    subject_id = Str(desc="FreeSurfer subject ID")


class SubjectSummary(SummaryInterface):
    """Subject html summary reportlet."""

    input_spec = _SubjectSummaryInputSpec
    output_spec = _SubjectSummaryOutputSpec

    def _run_interface(self, runtime):
        if isdefined(self.inputs.subject_id):
            self._results["subject_id"] = self.inputs.subject_id
        return super(SubjectSummary, self)._run_interface(runtime)

    def _generate_segment(self):
        if not isdefined(self.inputs.subjects_dir):
            freesurfer_status = "Not run"
        else:
            recon = fs.ReconAll(
                subjects_dir=self.inputs.subjects_dir,
                subject_id=self.inputs.subject_id,
                T1_files=self.inputs.t1w,
                flags="-noskullstrip",
            )
            if recon.cmdline.startswith("echo"):
                freesurfer_status = "Pre-existing directory"
            else:
                freesurfer_status = "Run by sMRIPrep"

        t2w_seg = ""
        if self.inputs.t2w:
            t2w_seg = "(+ {:d} T2-weighted)".format(len(self.inputs.t2w))

        output_spaces = self.inputs.output_spaces
        if not isdefined(output_spaces):
            output_spaces = "&lt;none given&gt;"
        else:
            output_spaces = ", ".join(output_spaces)

        return SUBJECT_TEMPLATE.format(
            subject_id=self.inputs.subject_id,
            n_t1s=len(self.inputs.t1w),
            t2w=t2w_seg,
            output_spaces=output_spaces,
            freesurfer_status=freesurfer_status,
        )


class _AboutSummaryInputSpec(BaseInterfaceInputSpec):
    version = Str(desc="sMRIPrep version")
    command = Str(desc="sMRIPrep command")
    # Date not included - update timestamp only if version or command changes


class AboutSummary(SummaryInterface):
    """About section reportlet."""

    input_spec = _AboutSummaryInputSpec

    def _generate_segment(self):
        return ABOUT_TEMPLATE.format(
            version=self.inputs.version,
            command=self.inputs.command,
            date=time.strftime("%Y-%m-%d %H:%M:%S %z"),
        )


class _FSSurfaceReportInputSpec(_SVGReportCapableInputSpec, _FSSourceInputSpec):
    pass


class _FSSurfaceReportOutputSpec(reporting.ReportCapableOutputSpec):
    pass


class FSSurfaceReport(SimpleInterface):
    """Replaces ``ReconAllRPT``, without need of calling recon-all."""

    input_spec = _FSSurfaceReportInputSpec
    output_spec = _FSSurfaceReportOutputSpec

    def _run_interface(self, runtime):
        from niworkflows.viz.utils import (
            plot_registration,
            cuts_from_bbox,
            compose_view,
        )
        from nibabel import load

        rootdir = Path(self.inputs.subjects_dir) / self.inputs.subject_id
        _anat_file = str(rootdir / "mri" / "brain.mgz")
        _contour_file = str(rootdir / "mri" / "ribbon.mgz")

        anat = load(_anat_file)
        contour_nii = load(_contour_file)

        n_cuts = 7
        cuts = cuts_from_bbox(contour_nii, cuts=n_cuts)

        self._results["out_report"] = str(Path(runtime.cwd) / self.inputs.out_report)

        # Call composer
        compose_view(
            plot_registration(
                anat,
                "fixed-image",
                estimate_brightness=True,
                cuts=cuts,
                contour=contour_nii,
                compress=self.inputs.compress_report,
            ),
            [],
            out_file=self._results["out_report"],
        )
        return runtime

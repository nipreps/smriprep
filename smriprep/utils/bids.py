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
"""Utilities to handle BIDS inputs."""
from collections import defaultdict
from pathlib import Path
from json import loads
from pkg_resources import resource_filename as pkgrf
from bids.layout import BIDSLayout
from bids.layout.writing import build_path


def get_outputnode_spec():
    """
    Generate outputnode's fields from I/O spec file.

    Examples
    --------
    >>> get_outputnode_spec()  # doctest: +NORMALIZE_WHITESPACE
    ['t1w_preproc', 't1w_mask', 't1w_dseg', 't1w_tpms',
    'std_preproc', 'std_mask', 'std_dseg', 'std_tpms',
    'anat2std_xfm', 'std2anat_xfm',
    't1w_aseg', 't1w_aparc',
    't1w2fsnative_xfm', 'fsnative2t1w_xfm',
    'surfaces', 'morphometrics']

    """
    spec = loads(Path(pkgrf("smriprep", "data/io_spec.json")).read_text())["queries"]
    fields = ["_".join((m, s)) for m in ("t1w", "std") for s in spec["baseline"].keys()]
    fields += [s for s in spec["std_xfms"].keys()]
    fields += [s for s in spec["surfaces"].keys()]
    return fields


def collect_derivatives(
    derivatives_dir, subject_id, std_spaces, freesurfer, spec=None, patterns=None
):
    """Gather existing derivatives and compose a cache."""
    if spec is None or patterns is None:
        _spec, _patterns = tuple(
            loads(Path(pkgrf("smriprep", "data/io_spec.json")).read_text()).values()
        )

        if spec is None:
            spec = _spec
        if patterns is None:
            patterns = _patterns

    derivs_cache = defaultdict(list, {})
    layout = BIDSLayout(derivatives_dir, config=["bids", "derivatives"])
    derivatives_dir = Path(derivatives_dir)

    def _check_item(item):
        if not item:
            return None

        if isinstance(item, str):
            item = [item]

        result = []
        for i in item:
            if not (derivatives_dir / i).exists():
                i = i.rstrip(".gz")
                if not (derivatives_dir / i).exists():
                    return None
            result.append(str(derivatives_dir / i))

        return result

    for k, q in spec["baseline"].items():
        q["subject"] = subject_id
        item = layout.get(return_type='filename', **q)
        if not item:
            continue

        derivs_cache["t1w_%s" % k] = item[0] if len(item) == 1 else item

    for space in std_spaces:
        for k, q in spec["std_xfms"].items():
            q["subject"] = subject_id
            q["from"] = q["from"] or space
            q["to"] = q["to"] or space
            item = layout.get(return_type='filename', **q)
            if not item:
                continue
            derivs_cache[k] += item

    derivs_cache = dict(derivs_cache)  # Back to a standard dictionary

    transforms = derivs_cache.setdefault('transforms', {})
    for space in std_spaces:
        for k, q in spec["transforms"].items():
            q = q.copy()
            q["subject"] = subject_id
            q["from"] = q["from"] or space
            q["to"] = q["to"] or space
            item = layout.get(return_type='filename', **q)
            if not item:
                continue
            transforms.setdefault(space, {})[k] = item[0] if len(item) == 1 else item

    if freesurfer:
        for k, q in spec["surfaces"].items():
            q["subject"] = subject_id
            item = _check_item(build_path(q, patterns))
            if not item:
                continue

            if len(item) == 1:
                item = item[0]
            derivs_cache[k] = item

    derivs_cache["template"] = std_spaces
    return derivs_cache


def write_bidsignore(deriv_dir):
    bids_ignore = [
        "*.html",
        "logs/",
        "figures/",  # Reports
        "*_xfm.*",  # Unspecified transform files
        "*.surf.gii",  # Unspecified structural outputs
    ]
    ignore_file = Path(deriv_dir) / ".bidsignore"

    ignore_file.write_text("\n".join(bids_ignore) + "\n")


def write_derivative_description(bids_dir, deriv_dir):
    """
    Write a ``dataset_description.json`` for the derivatives folder.

    .. testsetup::

    >>> from pkg_resources import resource_filename
    >>> from pathlib import Path
    >>> from tempfile import TemporaryDirectory
    >>> tmpdir = TemporaryDirectory()
    >>> bids_dir = resource_filename('smriprep', 'data/tests')
    >>> deriv_desc = Path(tmpdir.name) / 'dataset_description.json'

    .. doctest::

    >>> write_derivative_description(bids_dir, deriv_desc.parent)
    >>> deriv_desc.is_file()
    True

    .. testcleanup::

    >>> tmpdir.cleanup()


    """
    import os
    from pathlib import Path
    import json
    from ..__about__ import __version__, DOWNLOAD_URL

    bids_dir = Path(bids_dir)
    deriv_dir = Path(deriv_dir)
    desc = {
        "Name": "sMRIPrep - Structural MRI PREProcessing workflow",
        "BIDSVersion": "1.4.0",
        "DatasetType": "derivative",
        "GeneratedBy": [
            {
                "Name": "sMRIPrep",
                "Version": __version__,
                "CodeURL": DOWNLOAD_URL,
            }
        ],
        "HowToAcknowledge": "Please cite our paper (https://doi.org/10.1101/306951), and "
        "include the generated citation boilerplate within the Methods "
        "section of the text.",
    }

    # Keys that can only be set by environment
    if "SMRIPREP_DOCKER_TAG" in os.environ:
        desc["GeneratedBy"][0]["Container"] = {
            "Type": "docker",
            "Tag": f"poldracklab/smriprep:{os.environ['SMRIPREP_DOCKER_TAG']}",
        }
    if "SMRIPREP_SINGULARITY_URL" in os.environ:
        desc["GeneratedBy"][0]["Container"] = {
            "Type": "singularity",
            "URI": os.environ["SMRIPREP_SINGULARITY_URL"],
        }

    # Keys deriving from source dataset
    orig_desc = {}
    fname = bids_dir / "dataset_description.json"
    if fname.exists():
        orig_desc = json.loads(fname.read_text())

    if "DatasetDOI" in orig_desc:
        doi = orig_desc["DatasetDOI"]
        desc["SourceDatasets"] = [
            {
                "URL": f"https://doi.org/{doi}",
                "DOI": doi,
            }
        ]
    if "License" in orig_desc:
        desc["License"] = orig_desc["License"]

    Path.write_text(deriv_dir / "dataset_description.json", json.dumps(desc, indent=4))

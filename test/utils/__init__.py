# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
#
# Copyright The NiPreps Developers <nipreps@gmail.com>
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
from collections.abc import Iterable, Mapping

import yaml
from acres import Loader

load_data = Loader(__package__)

DERIV_SKELETON = load_data('derivatives.yml')
DERIV_GROUPS = list(yaml.safe_load(DERIV_SKELETON.read_text())['anat'])


def deriv_skeleton(
    include: Mapping[str, bool | int] | Iterable[str] | None = None,
    *,
    subject: str = '01',
    session: str | None = None,
) -> dict:
    """Build a :func:`~niworkflows.utils.testing.generate_bids_skeleton` layout.

    Parameters
    ----------
    include
        Groups from ``derivatives.yml`` to include. ``None`` includes all groups.
        A mapping may set a group to ``True`` (all files), ``False`` (no files),
        or an integer *n* (the first *n* files, e.g. one hemisphere of two).
    subject
        Subject label to place the derivatives under.
    session
        Session label, if any.
    """
    skeleton = yaml.safe_load(DERIV_SKELETON.read_text())
    groups = skeleton.pop('anat')

    if include is None:
        include = dict.fromkeys(groups, True)
    elif not isinstance(include, Mapping):
        include = dict.fromkeys(include, True)

    unknown = set(include) - set(groups)
    if unknown:
        raise KeyError(f'Unknown derivative groups: {sorted(unknown)}')

    anat = []
    for name, count in include.items():
        files = groups[name]
        # bool is an int subclass: True must mean "all", not "first one"
        anat.extend(files if count is True else files[: int(count)])

    contents = {'anat': anat}
    if session is not None:
        contents['session'] = session
    return {**skeleton, subject: [contents]}

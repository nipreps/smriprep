# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
"""Utilities to handle BIDS inputs."""
from collections import defaultdict
from pathlib import Path
from json import loads
from pkg_resources import resource_filename as pkgrf
from bids.layout.writing import build_path


def predict_derivatives(subject_id, output_spaces, freesurfer):
    """
    Generate a list of the files that should be found in the output folder.

    The prediction of outputs serves two purposes:

      * Anticipates the set of outputs that will be generated.
      * Informs the decision of whether the workflow should be staged or some
        sections can be skip.

    Parameters
    ----------
    subject_id : :obj:`str`
        A subject id
    output_spaces : :obj:`list`
        TemplateFlow identifiers of the requested output spaces
    freesurfer : :obj:`bool`
        Whether the ``--fs-no-reconall`` flag was used.

    Examples
    --------
    >>> predict_derivatives('01', ['MNI152NLin2009cAsym'], False)
    ['sub-01/anat/sub-01_desc-brain_mask.nii.gz',
     'sub-01/anat/sub-01_desc-preproc_T1w.nii.gz',
     'sub-01/anat/sub-01_dseg.nii.gz',
     'sub-01/anat/sub-01_from-MNI152NLin2009cAsym_to-T1w_mode-image_xfm.h5',
     'sub-01/anat/sub-01_from-T1w_to-MNI152NLin2009cAsym_mode-image_xfm.h5',
     'sub-01/anat/sub-01_label-CSF_probseg.nii.gz',
     'sub-01/anat/sub-01_label-GM_probseg.nii.gz',
     'sub-01/anat/sub-01_label-WM_probseg.nii.gz',
     'sub-01/anat/sub-01_space-MNI152NLin2009cAsym_desc-brain_mask.nii.gz',
     'sub-01/anat/sub-01_space-MNI152NLin2009cAsym_desc-preproc_T1w.nii.gz',
     'sub-01/anat/sub-01_space-MNI152NLin2009cAsym_dseg.nii.gz',
     'sub-01/anat/sub-01_space-MNI152NLin2009cAsym_label-CSF_probseg.nii.gz',
     'sub-01/anat/sub-01_space-MNI152NLin2009cAsym_label-GM_probseg.nii.gz',
     'sub-01/anat/sub-01_space-MNI152NLin2009cAsym_label-WM_probseg.nii.gz']

    """
    spec = loads(Path(pkgrf('smriprep', 'data/io_spec.json')).read_text())

    def _normalize_q(query, space=None):
        query = query.copy()
        query['subject'] = subject_id
        if space is not None:
            query['space'] = space
        if 'from' in query and not query['from']:
            query['from'] = output_spaces
        if 'to' in query and not query['to']:
            query['to'] = output_spaces
        return query

    queries = [_normalize_q(q, space=None)
               for q in spec['queries']['baseline'].values()]

    queries += [_normalize_q(q, space=s) for s in output_spaces
                for q in spec['queries']['baseline'].values()]
    queries += [_normalize_q(q) for q in spec['queries']['std_xfms'].values()]
    if freesurfer:
        queries += [_normalize_q(q)
                    for q in spec['queries']['surfaces'].values()]

    output = []
    for q in queries:
        paths = build_path(q, spec['patterns'])
        if isinstance(paths, str):
            output.append(paths)
        elif paths:
            output += paths

    return sorted(output)


def collect_derivatives(derivatives_dir, subject_id, std_spaces, freesurfer,
                        spec=None, patterns=None):
    """Gather existing derivatives and compose a cache."""
    if spec is None or patterns is None:
        _spec, _patterns = tuple(
            loads(Path(pkgrf('smriprep', 'data/io_spec.json')).read_text()).values())

        if spec is None:
            spec = _spec
        if patterns is None:
            patterns = _patterns

    derivs_cache = defaultdict(list, {})
    derivatives_dir = Path(derivatives_dir)

    def _check_item(item):
        if not item:
            return None

        if isinstance(item, str):
            item = [item]

        result = []
        for i in item:
            if not (derivatives_dir / i).exists():
                i = i.rstrip('.gz')
                if not (derivatives_dir / i).exists():
                    return None
            result.append(str(derivatives_dir / i))

        return result

    for space in [None] + std_spaces:
        for k, q in spec['baseline'].items():
            q['subject'] = subject_id
            if space is not None:
                q['space'] = space
            item = _check_item(build_path(q, patterns, strict=True))
            if not item:
                return None

            if space:
                derivs_cache["std_%s" % k] += item
            else:
                derivs_cache["t1w_%s" % k] = item[0]

    for space in std_spaces:
        for k, q in spec['std_xfms'].items():
            q['subject'] = subject_id
            q['from'] = q['from'] or space
            q['to'] = q['to'] or space
            item = _check_item(build_path(q, patterns))
            if not item:
                return None
            derivs_cache[k] += item

    derivs_cache = dict(derivs_cache)  # Back to a standard dictionary

    if freesurfer:
        for k, q in spec['surfaces'].items():
            q['subject'] = subject_id
            item = _check_item(build_path(q, patterns))
            if not item:
                return None

            if len(item) == 1:
                item = item[0]
            derivs_cache[k] = item

    derivs_cache['template'] = std_spaces
    return derivs_cache


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
    from ..__about__ import __version__, __url__, DOWNLOAD_URL

    bids_dir = Path(bids_dir)
    deriv_dir = Path(deriv_dir)
    desc = {
        'Name': 'sMRIPrep - Structural MRI PREProcessing workflow',
        'BIDSVersion': '1.1.1',
        'PipelineDescription': {
            'Name': 'sMRIPrep',
            'Version': __version__,
            'CodeURL': DOWNLOAD_URL,
        },
        'CodeURL': __url__,
        'HowToAcknowledge':
            'Please cite our paper (https://doi.org/10.1101/306951), and '
            'include the generated citation boilerplate within the Methods '
            'section of the text.',
    }

    # Keys that can only be set by environment
    if 'SMRIPREP_DOCKER_TAG' in os.environ:
        desc['DockerHubContainerTag'] = os.environ['SMRIPREP_DOCKER_TAG']
    if 'SMRIPREP_SINGULARITY_URL' in os.environ:
        singularity_url = os.environ['SMRIPREP_SINGULARITY_URL']
        desc['SingularityContainerURL'] = singularity_url

        singularity_md5 = _get_shub_version(singularity_url)
        if singularity_md5 is not None and singularity_md5 is not NotImplemented:
            desc['SingularityContainerMD5'] = _get_shub_version(singularity_url)

    # Keys deriving from source dataset
    orig_desc = {}
    fname = bids_dir / 'dataset_description.json'
    if fname.exists():
        with fname.open() as fobj:
            orig_desc = json.load(fobj)

    if 'DatasetDOI' in orig_desc:
        desc['SourceDatasetsURLs'] = ['https://doi.org/{}'.format(
            orig_desc['DatasetDOI'])]
    if 'License' in orig_desc:
        desc['License'] = orig_desc['License']

    with (deriv_dir / 'dataset_description.json').open('w') as fobj:
        json.dump(desc, fobj, indent=4)


def _get_shub_version(singularity_url):
    return NotImplemented

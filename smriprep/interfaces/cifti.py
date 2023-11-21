import json
import typing as ty
from pathlib import Path

import nibabel as nb
import numpy as np
from nibabel import cifti2 as ci
from nipype.interfaces.base import File, SimpleInterface, TraitedSpec, traits
from templateflow import api as tf


class _GenerateDScalarInputSpec(TraitedSpec):
    surface_target = traits.Enum(
        'fsLR',
        usedefault=True,
        desc='CIFTI surface target space',
    )
    grayordinates = traits.Enum('91k', '170k', usedefault=True, desc='Final CIFTI grayordinates')
    scalar_surfs = traits.List(
        File(exists=True),
        mandatory=True,
        desc='list of surface BOLD GIFTI files (length 2 with order [L,R])',
    )
    scalar_name = traits.Str(mandatory=True, desc='Name of scalar')


class _GenerateDScalarOutputSpec(TraitedSpec):
    out_file = File(desc='generated CIFTI file')
    out_metadata = File(desc='CIFTI metadata JSON')


class GenerateDScalar(SimpleInterface):
    """
    Generate a HCP-style CIFTI-2 image from scalar surface files.
    """

    input_spec = _GenerateDScalarInputSpec
    output_spec = _GenerateDScalarOutputSpec

    def _run_interface(self, runtime):
        surface_labels, metadata = _prepare_cifti(self.inputs.grayordinates)
        self._results['out_file'] = _create_cifti_image(
            self.inputs.scalar_surfs,
            surface_labels,
            self.inputs.scalar_name,
            metadata,
        )
        metadata_file = Path('dscalar.json').absolute()
        metadata_file.write_text(json.dumps(metadata, indent=2))
        self._results['out_metadata'] = str(metadata_file)
        return runtime


def _prepare_cifti(grayordinates: str) -> tuple[list, dict]:
    """
    Fetch the required templates needed for CIFTI-2 generation, based on input surface density.

    Parameters
    ----------
    grayordinates :
        Total CIFTI grayordinates (91k, 170k)

    Returns
    -------
    surface_labels
        Surface label files for vertex inclusion/exclusion.
    metadata
        Dictionary with BIDS metadata.

    Examples
    --------
    >>> surface_labels, metadata = _prepare_cifti('91k')
    >>> surface_labels  # doctest: +ELLIPSIS +NORMALIZE_WHITESPACE
    ['.../tpl-fsLR_hemi-L_den-32k_desc-nomedialwall_dparc.label.gii',
     '.../tpl-fsLR_hemi-R_den-32k_desc-nomedialwall_dparc.label.gii']
    >>> metadata # doctest: +ELLIPSIS +NORMALIZE_WHITESPACE
    {'Density': '91,282 grayordinates corresponding to all of the grey matter sampled at a \
2mm average vertex spacing...', 'SpatialReference': {'CIFTI_STRUCTURE_CORTEX_LEFT': ...}}

    """

    grayord_key = {
        '91k': {
            'surface-den': '32k',
            'tf-res': '02',
            'grayords': '91,282',
            'res-mm': '2mm',
        },
        '170k': {
            'surface-den': '59k',
            'tf-res': '06',
            'grayords': '170,494',
            'res-mm': '1.6mm',
        },
    }
    if grayordinates not in grayord_key:
        raise NotImplementedError(f'Grayordinates {grayordinates} is not supported.')

    total_grayords = grayord_key[grayordinates]['grayords']
    res_mm = grayord_key[grayordinates]['res-mm']
    surface_density = grayord_key[grayordinates]['surface-den']
    # Fetch templates
    surface_labels = [
        str(
            tf.get(
                'fsLR',
                density=surface_density,
                hemi=hemi,
                desc='nomedialwall',
                suffix='dparc',
                raise_empty=True,
            )
        )
        for hemi in ('L', 'R')
    ]

    tf_url = 'https://templateflow.s3.amazonaws.com'
    surfaces_url = (  # midthickness is the default, but varying levels of inflation are all valid
        f'{tf_url}/tpl-fsLR/tpl-fsLR_den-{surface_density}_hemi-%s_midthickness.surf.gii'
    )
    metadata = {
        'Density': (
            f'{total_grayords} grayordinates corresponding to all of the grey matter sampled at a '
            f'{res_mm} average vertex spacing on the surface'
        ),
        'SpatialReference': {
            'CIFTI_STRUCTURE_CORTEX_LEFT': surfaces_url % 'L',
            'CIFTI_STRUCTURE_CORTEX_RIGHT': surfaces_url % 'R',
        },
    }
    return surface_labels, metadata


def _create_cifti_image(
    scalar_surfs: tuple[str, str],
    surface_labels: tuple[str, str],
    scalar_name: str,
    metadata: ty.Optional[dict] = None,
):
    """
    Generate CIFTI image in target space.

    Parameters
    ----------
    scalar_surfs
        Surface scalar files (L,R)
    surface_labels
        Surface label files used to remove medial wall (L,R)
    metadata
        Metadata to include in CIFTI header
    scalar_name
        Name to apply to scalar map

    Returns
    -------
    out :
        BOLD data saved as CIFTI dtseries
    """
    brainmodels = []
    arrays = []

    for idx, hemi in enumerate(('left', 'right')):
        labels = nb.load(surface_labels[idx])
        mask = np.bool_(labels.darrays[0].data)

        struct = f'cortex_{hemi}'
        brainmodels.append(
            ci.BrainModelAxis(struct, vertex=np.nonzero(mask)[0], nvertices={struct: len(mask)})
        )

        morph_scalar = nb.load(scalar_surfs[idx])
        arrays.append(morph_scalar.darrays[0].data[mask].astype('float32'))

    # provide some metadata to CIFTI matrix
    if not metadata:
        metadata = {
            'surface': 'fsLR',
        }

    # generate and save CIFTI image
    hdr = ci.Cifti2Header.from_axes(
        (ci.ScalarAxis([scalar_name]), brainmodels[0] + brainmodels[1])
    )
    hdr.matrix.metadata = ci.Cifti2MetaData(metadata)

    img = ci.Cifti2Image(dataobj=np.atleast_2d(np.concatenate(arrays)), header=hdr)
    img.nifti_header.set_intent('NIFTI_INTENT_CONNECTIVITY_DENSE_SCALARS')

    stem = Path(scalar_surfs[0]).name.split('.')[0]
    cifti_stem = '_'.join(ent for ent in stem.split('_') if not ent.startswith('hemi-'))
    out_file = Path.cwd() / f'{cifti_stem}.dscalar.nii'
    img.to_filename(out_file)
    return out_file

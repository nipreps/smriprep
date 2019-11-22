"""sMRIPrep settings."""
from templateflow.api import templates as _get_templates

TF_TEMPLATES = tuple(_get_templates())
LEGACY_SPACES = ('fsnative', 'fsaverage4', 'fsaverage5',
                 'fsaverage6', 'fsaverage')

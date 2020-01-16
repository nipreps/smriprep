# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
"""CLI Utilities."""
from argparse import Action
from ..conf import TF_TEMPLATES as _TF_TEMPLATES, LEGACY_SPACES


class ParseTemplates(Action):
    """Manipulate a string of templates with modifiers."""

    EXCEPTIONS = tuple()

    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, _template(values))

    @classmethod
    def set_nonstandard_spaces(cls, inlist):
        """Set permissible nonstandard spaces names."""
        if isinstance(inlist, str):
            inlist = [inlist]

        cls.EXCEPTIONS = tuple(inlist)


def _template(inlist):
    """Return a list of tuples composed of (template, template_specs)"""
    if isinstance(inlist, str):
        inlist = [inlist]

    templates = []
    for item in inlist:
        templates.extend(output_space(item))

    return templates


def output_space(value):
    """Parse one element of ``--output-spaces``."""
    tpl_args = value.split(':')
    template = tpl_args[0]
    spaces = []
    for modifier in tpl_args[1:]:
        spec = {}
        mitems = modifier.split('-', 1)
        spec[mitems[0]] = len(mitems) == 1 or mitems[1]
        spaces.append((template, spec))

    if template in ParseTemplates.EXCEPTIONS or template in LEGACY_SPACES:
        return [(template, {})]

    if template not in _TF_TEMPLATES:
        raise ValueError("""\
Template identifier "{}" not found. Please, make sure TemplateFlow is \
correctly installed and contains the given template identifiers.""".format(template))

    if not spaces:
        spaces.append((template, {}))
    return spaces

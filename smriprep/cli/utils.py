# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
"""CLI Utilities."""
from argparse import Action
from ..conf import TF_TEMPLATES as _TF_TEMPLATES

EXCEPTIONS = None


class ParseTemplates(Action):
    """Manipulate a string of templates with modifiers."""

    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, _template(values))


def _template(inlist):
    """Return an OrderedDict with templates."""
    from collections import OrderedDict
    if isinstance(inlist, str):
        inlist = [inlist]

    templates = []
    for item in reversed(inlist):
        templates.append(output_space(item))

    return OrderedDict(reversed(OrderedDict(templates).items()))


def output_space(value):
    """Parse one element of ``--output-spaces``."""
    global EXCEPTIONS
    tpl_args = value.split(':')
    template = tpl_args[0]
    spec = {}
    for modifier in tpl_args[1:]:
        mitems = modifier.split('-', 1)
        spec[mitems[0]] = len(mitems) == 1 or mitems[1]

    if EXCEPTIONS and template in EXCEPTIONS:
        return template, None

    if template not in _TF_TEMPLATES:
        raise ValueError("""\
Template identifier "{}" not found. Please, make sure TemplateFlow is \
correctly installed and contains the given template identifiers.""".format(template))

    return template, spec


def set_nonstandard_spaces(inlist):
    """Set permissible nonstandard spaces names."""
    global EXCEPTIONS
    if isinstance(inlist, str):
        inlist = [inlist]

    EXCEPTIONS = tuple(inlist)

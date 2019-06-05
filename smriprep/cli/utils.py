# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
"""
CLI Utilities
"""
from argparse import Action


class ParseTemplates(Action):
    """Manipulate a string of templates with modifiers"""

    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, _template(values))


def _template(inlist):
    """
    Return an OrderedDict with templates


    >>> list(_template(['MNI152NLin2009c']).keys())
    ['MNI152NLin2009c']

    >>> _template(['MNI152NLin2009c', 'MNI152NLin2009c:res-2'])
    OrderedDict([('MNI152NLin2009c', {})])

    >>> _template(['MNI152NLin2009c', 'MNI152NLin2009c:res-2',
    ...            'MNI152NLin6Asym:res-2', 'MNI152NLin6Asym'])
    OrderedDict([('MNI152NLin2009c', {}), ('MNI152NLin6Asym', {'res': '2'})])

    """
    from collections import OrderedDict
    if isinstance(inlist, str):
        inlist = [inlist]

    templates = []
    for item in reversed(inlist):
        templates.append(output_space(item))

    return OrderedDict(reversed(OrderedDict(templates).items()))


def output_space(value):
    """Parse one element of ``--output-spaces``.

    >>> output_space('MNI152NLin2009cAsym')
    ('MNI152NLin2009cAsym', {})

    >>> output_space('MNI152NLin2009cAsym:native')
    ('MNI152NLin2009cAsym', {'native': True})

    >>> output_space('MNI152NLin2009cAsym:res-2')
    ('MNI152NLin2009cAsym', {'res': '2'})

    >>> output_space('MNIInfant:res-2:cohort-1')
    ('MNIInfant', {'res': '2', 'cohort': '1'})

    """
    tpl_args = value.split(':')
    template = tpl_args[0]
    spec = {}
    for modifier in tpl_args[1:]:
        mitems = modifier.split('-', 1)
        spec[mitems[0]] = len(mitems) == 1 or mitems[1]

    return template, spec

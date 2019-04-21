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
        item = item.split(':')
        tpl_arg = (item[0], {})
        for i in item[1:]:
            modifier = i.split('-', 1)
            tpl_arg[1][modifier[0]] = modifier[1] if len(modifier) == 2 else None
        templates.append(tpl_arg)

    return OrderedDict(reversed(OrderedDict(templates).items()))

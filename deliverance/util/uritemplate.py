"""
A simple implementation of URI templates.  Note: this is incomplete!

This only implements simple {var} substitution, not any of the other
operations in the URI template (unfinished) spec.
"""
import re

__all__ = ['uri_template_substitute']

_uri_var_re = re.compile(r'\{(.*?)\}')

def uri_template_substitute(uri_template, vars):
    """Does URI template substitution
    
    This only substitutes simple ``{var}``, none of the fancier
    substitution techniques.
    """
    def subber(match):
        try:
            return vars[match.group(1)]
        except KeyError:
            raise KeyError('No variable {%s} in uri_template %r'
                           % (match.group(1), uri_template))
    return _uri_var_re.sub(subber, uri_template)

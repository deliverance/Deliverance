"""Converters for boolean and HTML"""

__all__ = ['asbool', 'html_quote']

def asbool(obj):
    """Converts a string to a boolean

    This converts the values "true", "t", "yes", "y", "on", and "1"
    into true, and "false", "f", "no", "n", "off" and "0" into false.
    Non-string values are left alone.  Other strings are errors.
    """
    if isinstance(obj, (str, unicode)):
        obj = obj.strip().lower()
        if obj in ['true', 'yes', 'on', 'y', 't', '1']:
            return True
        elif obj in ['false', 'no', 'off', 'n', 'f', '0']:
            return False
        else:
            raise ValueError(
                "String is not true/false: %r" % obj)
    return bool(obj)

from cgi import escape as cgi_escape
def html_quote(s):
    """HTML quotes the string"""
    s = unicode(s)
    return cgi_escape(s, True)

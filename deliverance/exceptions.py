"""
Exceptions for use throughout Deliverance
"""

import sys

class DeliveranceError(Exception):
    """
    Superclass for all deliverance exceptions

    In addition to a message, this can have a `request` and `element`
    attached to it.  Elements are the objects (maybe XML, or maybe
    not) that is applicable.
    """
    def __init__(self, msg=None, request=None, element=None, 
                 source_location=None):
        Exception.__init__(self, msg)
        self.request = request
        self.element = element
        self.source_location = source_location

class DeliveranceSyntaxError(DeliveranceError):
    """
    Exception raised when there is a syntax error in some file
    """

class AbortTheme(Exception):
    """
    Raised (and caught) when the theming of a request should be
    aborted.
    """

class AbortProxy(Exception):
    """
    Raised (and caught) when a proxy rule should be ignored
    """

def add_exception_info(info, exc_info=None):
    """
    Add the given information to the exception (typically context information)
    """
    if exc_info is None:
        exc_info = sys.exc_info()
    exc_class, exc, tb = exc_info
    if isinstance(exc_class, basestring):
        # Not much we can do here, but...
        exc_class += ' '+info
        return exc_class, exc, tb
    prev_message = str(exc)
    args = getattr(exc, 'args', None)
    if args is not None:
        if len(args) != 1 or not isinstance(args[0], basestring):
            args = tuple(args) + (info,)
            exc.args = args
        else:
            arg = '%s: %s' % (args[0], info)
            exc.args = (arg,)
    if args is None or str(exc) == prev_message:
        # This exception doesn't show information; revert:
        exc.args = exc.args[:-1]
        exc = Exception('%s (%s): %s' % (exc, exc.__class__.__name__, info))
    return exc_class, exc, tb
        
        

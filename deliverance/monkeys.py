import logging
from rfc822 import parsedate_tz, mktime_tz
from paste.httpexceptions import HTTPBadRequest

_applied = False

# This fixed the parser to handle OverflowError as well. See
# http://trac.pythonpaste.org/pythonpaste/ticket/398 for the relevant bugreport.
def DateHeader_parse(self, *args, **kwargs):
    """ return the time value (in seconds since 1970) """
    value = self.__call__(*args, **kwargs)
    if value:
        try:
            return mktime_tz(parsedate_tz(value))
        except (OverflowError, TypeError):
            raise HTTPBadRequest((
                "Received an ill-formed timestamp for %s: %s\r\n") %
                (self.name, value))


def apply():
    global _applied

    if _applied:
        return

    logging.info("Monkey-patching Paste to work around http://trac.pythonpaste.org/pythonpaste/ticket/398")
    from paste.httpheaders import _DateHeader
    _DateHeader.parse = DateHeader_parse

    _applied = True


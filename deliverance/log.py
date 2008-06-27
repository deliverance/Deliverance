"""
Logging for deliverance.

This does not use the standard :mod:`logging` module because that
module is not easily applied and inspected locally.  We want the log
messages to be strictly per-request.
"""

import logging
from lxml.etree import tostring, _Element

class SavingLogger(object):
    """
    Logger that saves all its messages locally.
    """
    def __init__(self, request, description=True):
        self.messages = []
        if description:
            self.descriptions = []
            self.describe = self.add_description
        else:
            self.describe = None
    def add_description(self, msg):
        self.descriptions.append(msg)
    def message(self, level, el, msg, *args, **kw):
        if args:
            msg = msg % args
        elif kw:
            msg = msg % kw
        self.messages.append((level, el, msg))
        return msg
    def debug(self, el, msg, *args, **kw):
        self.message(logging.DEBUG, el, msg, *args, **kw)
    def info(self, el, msg, *args, **kw):
        self.message(logging.INFO, el, msg, *args, **kw)
    def notify(self, el, msg, *args, **kw):
        self.message(logging.INFO+1, el, msg, *args, **kw)
    def warn(self, el, msg, *args, **kw):
        self.message(logging.WARN, el, msg, *args, **kw)
    warning = warn
    def error(self, el, msg, *args, **kw):
        self.message(logging.ERROR, el, msg, *args, **kw)
    def fatal(self, el, msg, *args, **kw):
        self.message(logging.FATAL, el, msg, *args, **kw)

class PrintingLogger(SavingLogger):

    def __init__(self, request, description=True, print_level=logging.DEBUG):
        super(PrintingLogger, self).__init__(request, description=description)
        self.print_level = print_level

    def add_description(self, msg):
        print 'description:', msg
        super(PrintingLogger, self).add_description(msg)

    def message(self, level, el, msg, *args, **kw):
        msg = super(PrintingLogger, self).message(level, el, msg, *args, **kw)
        if level >= self.print_level:
            if isinstance(el, _Element):
                s = tostring(el)
            else:
                s = str(el)
            print '%s (%s)' % (msg, s)
        return msg

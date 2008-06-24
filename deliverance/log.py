import logging

class SavingLogger(object):
    def __init__(self, description=True):
        self.messages = []
        if description:
            self.descriptions = []
            self.describe = self.add_description
    def add_description(self, msg):
        self.descriptions.append(msg)
    def message(self, level, el, msg, *args, **kw):
        if args:
            msg = msg % args
        elif kw:
            msg = msg % kw
        self.messages.append((level, el, msg))
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

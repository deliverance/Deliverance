# see ticket #36

import re

SPECIAL_CHARACTERS = (
    (">", "__GT__"),
    ("<", "__LT__"),
    ("&", "__AMP__"),
    )

class Escaper(object):
    def __init__(self, inners):
        self.index = 0
        self.inners = inners
        self.pattern = r'__START_CDATA__%s__END_CDATA__'

    def replace(self, string):
        for char in SPECIAL_CHARACTERS:
            string = string.replace(char[0], char[1])
        return string

    def __call__(self, matchobj):
        inner = self.inners[self.index]
        inner = self.replace(inner)
        self.index += 1
        return self.pattern % inner

class Unescaper(Escaper):
    def __init__(self, inners):
        Escaper.__init__(self, inners)
        self.pattern = r"<![CDATA[%s]]>"

    def replace(self, string):
        for char in SPECIAL_CHARACTERS:
            string = string.replace(char[1], char[0])
        return string

def escape_cdata(s):
    cdata_re = re.compile(r'<!\[CDATA\[(.*?)\]\]>', re.DOTALL)
    inners = cdata_re.findall(s)
    if not inners:
        return s
    repl = Escaper(inners)
    return cdata_re.sub(repl, s)

def unescape_cdata(s):
    cdata_re = re.compile(r'__START_CDATA__(.*?)__END_CDATA__', re.DOTALL)
    inners = cdata_re.findall(s)
    if not inners:
        return s
    repl = Unescaper(inners)
    return cdata_re.sub(repl, s)

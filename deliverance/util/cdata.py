# see ticket #36

import re

def escape_cdata(s):
    cdata_re = re.compile(r'<!\[CDATA\[(.*?)\]\]>', re.DOTALL)
    return cdata_re.sub(r'__START_CDATA__\1__END_CDATA__', s)

def unescape_cdata(s):
    cdata_re = re.compile(r'__START_CDATA__(.*?)__END_CDATA__', re.DOTALL)
    return cdata_re.sub(r'<![CDATA[\1]]>', s)

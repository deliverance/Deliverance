# see ticket #12

import re

META_CHARSET_TAG = re.compile(
    """(<meta[^>]*charset=["']?(?P<charset>[^"'>]*)["']?[ ]?[/]?[>])""",
    re.IGNORECASE|re.DOTALL)
HEAD_TAG = re.compile('<head>', re.IGNORECASE)

def fix_meta_charset_position(s):
    """
    Move tag with charset definition to be first child of head tag.
    """
    data = META_CHARSET_TAG.search(s)
    if data:
        tag = data.group()
        s = META_CHARSET_TAG.sub('',s)
        s = HEAD_TAG.sub('<head>'+tag, s)

    return s

def force_charset(resp, default="utf8"):
    """
    Sets the charset of the response, to guarantee that
    ``resp.unicode_body`` won't raise AttributeError:

     1. If the charset is already set, leave it.

     2. If a charset declaration is found in the
        response body, use it.

     3. Otherwise use ``default``.
    """
    if resp.charset:
        return resp
    match = META_CHARSET_TAG.search(resp.body)
    if match is None:
        resp.charset = default
        return resp
    charset = match.group('charset')
    resp.charset = charset
    return resp

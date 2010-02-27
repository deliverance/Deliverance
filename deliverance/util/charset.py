# see ticket #12

import re

META_CHARSET_TAG = re.compile("""(<meta[^>]*charset=["']*[^"'>]*["']*[>])""", re.IGNORECASE|re.DOTALL)
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

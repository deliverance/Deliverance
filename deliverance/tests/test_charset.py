from deliverance.util.charset import META_CHARSET_TAG
from nose.tools import assert_true, assert_false, assert_equals

docs = {
    """<meta http-equiv="Content-Type" content="text/html; charset=UTF-8">""": "UTF-8",
    """<meta http-equiv="Content-Type" content="text/html; charset=ASCII"></meta>""": "ASCII",
    """<meta http-equiv="Content-Type" content="text/html; charset=ISO-8859-1"/>""": "ISO-8859-1",
    """<meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />""": "UTF-8",
    """<meta http-equiv="Content-Type" content="text/html; charset=UTF-8" >""": "UTF-8",
    """<meta charset="UTF-8" >""": "UTF-8",
    """<meta charset="UTF-8" />""": "UTF-8",
    """<meta charset="UTF-8">""": "UTF-8",

    # it's not completely strict; these are OK too:
    """<meta charset="UTF-8>""": "UTF-8",
    """<meta charset='UTF-8">""": "UTF-8",
}

bad_docs = [
    """<meta http-equiv="Content-Type" content="text/html; charset=UTF-8"  >""", # nobody needs that much whitespace, right?
    """<meta http-equiv="Content-Type" content="text/html; charset=UTF-8"//>""", # only one trailing slash allowed
    """<meta http-equiv="Content-Type" content="text/html; charset='ASCII'"></meta>""", # shouldn't have nested quotes
    """<meta http-equiv="Content-Type" content="text/html; charset=ASCII""></meta>""", # can have only one trailing quote!
    """<meta http-equiv="Content-Type" content="text/html"> <foo charset=UTF-8" >""", # has to be in the meta tag
    """<meta http-equiv="Content-Type" content="text/html"> charset=UTF-8" >""", # really .. has to be in the meta tag
]

def test_regex():
    for doc in docs:
        should_match(doc, docs[doc])
    for doc in bad_docs:
        shouldnt_match(doc)

def shouldnt_match(doc):
    match = META_CHARSET_TAG.search(doc)
    assert_false(match)

def should_match(doc, charset):
    match = META_CHARSET_TAG.search(doc)
    assert_true(match)
    assert_equals(match.group('charset'), charset)

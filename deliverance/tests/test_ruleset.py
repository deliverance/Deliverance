from deliverance.ruleset import RuleSet
from lxml.html import tostring, document_fromstring
from nose.tools import assert_equals


def test_make_links_absolute():
    href_transformations = [
        ('#', '#'),
        ('#top', '#top'),
        ('', ''),
        ('relative', 'http://localhost/path/relative'),
        ('/', 'http://localhost/'),
        ('.', 'http://localhost/path/'),
        ('/another/path', 'http://localhost/another/path'),
        ('http://somehost/', 'http://somehost/'),
        ]
    for href, expected in href_transformations:
        yield check_href, href, expected


def check_href(href, expected):
    ruleset = RuleSet(None, None, None, None)
    html = '<html><body><a href="%s">link</a></body></html>'
    doc = document_fromstring(html % href,
                              base_url='http://localhost/path/theme.html')

    ruleset.make_links_absolute(doc)

    assert_equals(tostring(doc), html % expected)

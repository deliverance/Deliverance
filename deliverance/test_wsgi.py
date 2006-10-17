import os
import sys
from lxml import etree
from paste.fixture import TestApp
from paste.urlparser import StaticURLParser
from wsgifilter import DeliveranceMiddleware
from formencode.doctest_xml_compare import xml_compare
from htmlserialize import tostring

static_data = os.path.join(os.path.dirname(__file__), 'test-data', 'static')
tasktracker_data = os.path.join(os.path.dirname(__file__), 'test-data', 'tasktracker')
nycsr_data = os.path.join(os.path.dirname(__file__), 'test-data', 'nycsr')

static_app = StaticURLParser(static_data)
tasktracker_app = StaticURLParser(tasktracker_data)
nycsr_app = StaticURLParser(nycsr_data)

def html_string_compare(astr, bstr):
    def reporter(x):
        print x

    a = None
    b = None
    try:
        a = etree.HTML(astr)
    except:
        print a
        raise
    try:
        b = etree.HTML(bstr)
    except:
        print b
        raise

    reporter = []
    result = xml_compare(a, b, reporter.append)
    if not result:
        raise ValueError(
            "Comparison failed between actual:\n==================\n%s\n\nexpected:\n==================\n%s\n\nReport:\n%s"
            % (astr, bstr, '\n'.join(reporter)))

def test_basic():
    wsgi_app = DeliveranceMiddleware(static_app, 'theme.html', 'rules.xml')
    app = TestApp(wsgi_app)
    res = app.get('/example.html')
    res2 = app.get('/example_expected.html?notheme')
    html_string_compare(res.body, res2.body)

def test_text():
    wsgi_app = DeliveranceMiddleware(static_app, 'theme.html', 'text-rules.xml')
    app = TestApp(wsgi_app)
    res = app.get('/example.html')
    res2 = app.get('/texttest_expected.html?notheme')
    html_string_compare(res.body, res2.body)

def test_tasktracker():
    wsgi_app = DeliveranceMiddleware(tasktracker_app, 'http://www.nycsr.org/nyc/video.php', 'tasktracker.xml')
    app = TestApp(wsgi_app)
    res = app.get('/content.html')
    res2 = app.get('/expected.html?notheme')
    html_string_compare(res.body, res2.body)


def test_xinclude():
    wsgi_app = DeliveranceMiddleware(static_app, 'xinclude_theme.html', 'xinclude_rules.xml')
    app = TestApp(wsgi_app)
    res = app.get('/example.html')
    res2 = app.get('/xinclude_expected.html?notheme')
    html_string_compare(res.body, res2.body)


def test_nycsr():
    wsgi_app = DeliveranceMiddleware(nycsr_app, 'http://www.nycsr.org','nycsr.xml')
    app = TestApp(wsgi_app)
    res = app.get('/openplans.html')
    res2 = app.get('/nycsr_expected.html?notheme')
    html_string_compare(res.body, res2.body)


if __name__ == '__main__':
    pass


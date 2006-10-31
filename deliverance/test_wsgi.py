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
necoro_data = os.path.join(os.path.dirname(__file__), 'test-data', 'necoro')
guidesearch_data = os.path.join(os.path.dirname(__file__), 'test-data', 'guidesearch')
ajax_data = os.path.join(os.path.dirname(__file__), 'test-data', 'ajax')

static_app = StaticURLParser(static_data)
tasktracker_app = StaticURLParser(tasktracker_data)
nycsr_app = StaticURLParser(nycsr_data)
necoro_app = StaticURLParser(necoro_data)
guidesearch_app = StaticURLParser(guidesearch_data)
ajax_app = StaticURLParser(ajax_data)


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



def do_basic(renderer_type, name):
    wsgi_app = DeliveranceMiddleware(static_app, 'theme.html', 'rules.xml',
                                     renderer_type)
    app = TestApp(wsgi_app)
    res = app.get('/example.html')
    res2 = app.get('/example_expected.html?notheme')
    html_string_compare(res.body, res2.body)

def do_text(renderer_type, name):
    wsgi_app = DeliveranceMiddleware(static_app, 'theme.html', 'text-rules.xml',
                                     renderer_type)
    app = TestApp(wsgi_app)
    res = app.get('/example.html')
    res2 = app.get('/texttest_expected.html?notheme')
    html_string_compare(res.body, res2.body)

def do_tasktracker(renderer_type, name):
    wsgi_app = DeliveranceMiddleware(tasktracker_app, 'http://www.nycsr.org/nyc/video.php', 
                                     'tasktracker.xml',renderer_type)
    app = TestApp(wsgi_app)
    res = app.get('/content.html')
    res2 = app.get('/expected.html?notheme')
    html_string_compare(res.body, res2.body)


def do_xinclude(renderer_type, name):
    wsgi_app = DeliveranceMiddleware(static_app, 'xinclude_theme.html', 'xinclude_rules.xml',
                                     renderer_type)
    app = TestApp(wsgi_app)
    res = app.get('/example.html')
    res2 = app.get('/xinclude_expected.html?notheme')
    html_string_compare(res.body, res2.body)


def do_nycsr(renderer_type, name):
    wsgi_app = DeliveranceMiddleware(nycsr_app, 'http://www.nycsr.org','nycsr.xml',
                                     renderer_type)
    app = TestApp(wsgi_app)
    res = app.get('/openplans.html')
    res2 = app.get('/nycsr_expected.html?notheme')
    html_string_compare(res.body, res2.body)


def do_necoro(renderer_type, name):
    wsgi_app = DeliveranceMiddleware(necoro_app, 'theme.html','necoro.xml', renderer_type)
    app = TestApp(wsgi_app)
    res = app.get('/zope.html')
    res2 = app.get('/expected.html?notheme')
    html_string_compare(res.body, res2.body)

def do_guidesearch(renderer_type, name):
    wsgi_app = DeliveranceMiddleware(guidesearch_app, 'theme.html','guidesearch.xml', renderer_type)
    app = TestApp(wsgi_app)
    res = app.get('/zope.html')
    res2 = app.get('/expected.html?notheme')
    html_string_compare(res.body, res2.body)

def do_ajax(renderer_type, name):
    wsgi_app = DeliveranceMiddleware(ajax_app, 'theme.html','rules.xml', renderer_type)
    app = TestApp(wsgi_app)
    res = app.get('/content.html')
    res2 = app.get('/content.html?notheme')
    html_string_compare(res.body, res2.body)


RENDERER_TYPES = ['py', 'xslt']
TEST_FUNCS = [ do_basic, do_text, do_tasktracker, do_xinclude, do_nycsr, do_necoro, do_guidesearch ] 
def test_all():
    for renderer_type in RENDERER_TYPES:
        for test_func in TEST_FUNCS: 
            yield test_func, renderer_type, test_func.func_name
            

if __name__ == '__main__':
    pass


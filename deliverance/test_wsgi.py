import os
import sys
from lxml import etree
from paste.fixture import TestApp
from paste.urlparser import StaticURLParser
from paste.response import header_value
from paste.wsgilib import intercept_output
from deliverance.wsgimiddleware import DeliveranceMiddleware
from formencode.doctest_xml_compare import xml_compare
from deliverance.htmlserialize import tostring
from deliverance.cache_fixture import CacheFixtureResponseInfo, CacheFixtureApp
from deliverance import cache_utils
from time import time as now
from rfc822 import formatdate

static_data = os.path.join(os.path.dirname(__file__), 'test-data', 'static')
tasktracker_data = os.path.join(os.path.dirname(__file__), 'test-data', 'tasktracker')
nycsr_data = os.path.join(os.path.dirname(__file__), 'test-data', 'nycsr')
necoro_data = os.path.join(os.path.dirname(__file__), 'test-data', 'necoro')
guidesearch_data = os.path.join(os.path.dirname(__file__), 'test-data', 'guidesearch')
ajax_data = os.path.join(os.path.dirname(__file__), 'test-data', 'ajax')
url_data = os.path.join(os.path.dirname(__file__), 'test-data', 'wsgiurl')
aggregate_data = os.path.join(os.path.dirname(__file__), 'test-data', 'aggregate')
aggregate2_data = os.path.join(os.path.dirname(__file__), 'test-data', 'aggregate2')
ignore_data = os.path.join(os.path.dirname(__file__), 'test-data', 'ignore')
urienv_data = os.path.join(os.path.dirname(__file__), 'test-data', 'urienv')

static_app = StaticURLParser(static_data)
tasktracker_app = StaticURLParser(tasktracker_data)
nycsr_app = StaticURLParser(nycsr_data)
necoro_app = StaticURLParser(necoro_data)
guidesearch_app = StaticURLParser(guidesearch_data)
ajax_app = StaticURLParser(ajax_data)
url_app = StaticURLParser(url_data)
aggregate_app = StaticURLParser(aggregate_data)
aggregate2_app = StaticURLParser(aggregate2_data)
ignore_app = StaticURLParser(ignore_data)
urienv_app = StaticURLParser(urienv_data)

def html_string_compare(astr, bstr):
    """
    compare to strings containing html based on html 
    equivalence. Raises ValueError if the strings are 
    not equivalent. 
    """

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
    wsgi_app = DeliveranceMiddleware(tasktracker_app, 'http://codespeak.net/svn/z3/deliverance/trunk/deliverance/test-data/nycsr/nycsr_theme.html', 
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

def do_with_spaces(renderer_type, name):
    wsgi_app = DeliveranceMiddleware(static_app, 'xinclude_theme.html', 'xinclude_rules.xml',
                                     renderer_type)
    app = TestApp(wsgi_app)
    expected = app.get('/xinclude_expected.html?notheme').body
    res = app.get('/example%20with%20spaces.html')
    html_string_compare(res.body, expected)
    wsgi_app = DeliveranceMiddleware(static_app, 'xinclude_theme.html', 'xinclude_rules%20with%20spaces.xml',
                                     renderer_type)
    app = TestApp(wsgi_app)
    res2 = app.get('/example.html')
    html_string_compare(res2.body, expected)

def do_nycsr(renderer_type, name):
    wsgi_app = DeliveranceMiddleware(nycsr_app, 'http://codespeak.net/svn/z3/deliverance/trunk/deliverance/test-data/nycsr/nycsr_theme.html','nycsr.xml',
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

def do_url(renderer_type, name):
    wsgi_app = DeliveranceMiddleware(url_app, '/foo/bar/test_url_theme.html','/foo/bar/test_url.xml', renderer_type)
    app = TestApp(wsgi_app)
    res = app.get('/foo/bar/test_url_content.html')
    res2 = app.get('/foo/bar/test_url_expected.html?notheme')
    html_string_compare(res.body,res2.body)

def do_aggregate(renderer_type, name):
    wsgi_app = DeliveranceMiddleware(aggregate_app, 'theme.html', 'rules.xml',
                                     renderer_type)
    app = TestApp(wsgi_app)
    res = app.get('/example.html')
    res2 = app.get('/expected.html?notheme')
    html_string_compare(res.body, res2.body)

def do_aggregate2(renderer_type, name):
    wsgi_app = DeliveranceMiddleware(aggregate2_app, 'theme.html', 'rules.xml',
                                     renderer_type)
    app = TestApp(wsgi_app)
    res = app.get('/index.html')
    res2 = app.get('/expected.html?notheme')
    html_string_compare(res.body, res2.body)

def do_ignore(renderer_type, name):
    ## FIXME: there are no files in test-data/ignore/, where this comes from.
    return
    wsgi_app = DeliveranceMiddleware(ignore_app, 'theme.html', 'rules.xml', 
                                     renderer_type)
    
    app = TestApp(wsgi_app)
    res = app.get('/index.html')
    res2 = app.get('/expected.html?notheme')
    html_string_compare(res.body, res2.body)

    res = app.get('/index2.html')
    res2 = app.get('/expected2.html?notheme')
    html_string_compare(res.body, res2.body)


def do_ignore_header(renderer_type, name):     
    ## FIXME: there are no files in test-data/ignore/, where this comes from.
    return
    class NoThemeHeaderApp:
        def __init__(self, app): 
            self.app = app

        def __call__(self, environ, start_response): 
            status, headers, body = intercept_output(environ, self.app)
            headers.append(('x-deliverance-no-theme','1'))
            start_response(status, headers)
            return [body]

    wsgi_app = DeliveranceMiddleware(NoThemeHeaderApp(ignore_app), 
                                      'theme.html', 'rules.xml', 
                                      renderer_type)
    
    app = TestApp(wsgi_app)

    res = app.get('/index2.html')
    res2 = app.get('/expected3.html?notheme')
    html_string_compare(res.body, res2.body)
    
    

def do_cache(renderer_type, name): 
    # XXX this should be busted up into multiple tests I spose 

    theme_data = """ 
        <html>
          <head><title>theme</title></head>
          <body><div id="replaceme"></div></body>
        </html>
    """
    rule_data = """ 
        <rules xmlns="http://www.plone.org/deliverance">
          <replace theme="//*[@id='replaceme']" content="//*[@id='content']" />
        </rules>
    """
    
    content_data = """
         <html><head></head><body><div id="content">foo</div></body></html>
    """

    expected_data = """
        <html>
          <head>
            <meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
            <title>theme</title></head>
          <body><div id="content">foo</div></body>
        </html>
    """

    theme_info = CacheFixtureResponseInfo(theme_data)
    rule_info = CacheFixtureResponseInfo(rule_data)
    content_info = CacheFixtureResponseInfo(content_data)
    expected_info = CacheFixtureResponseInfo(expected_data)

    capp = CacheFixtureApp()
    capp.map_url('/theme.html',theme_info)
    capp.map_url('/rules.xml',rule_info)
    capp.map_url('/content.html',content_info)
    capp.map_url('/expected.html',expected_info)

    wsgi_app = DeliveranceMiddleware(capp, '/theme.html', '/rules.xml', 
                                     renderer_type)

    # check that everything works straight up 
    app = TestApp(wsgi_app)
    res = app.get('/content.html')
    res2 = app.get('/expected.html?notheme')
    html_string_compare(res.body, res2.body)

    # set some etags on the fixture 
    theme_info.etag = "theme_etag"
    rule_info.etag = "rule_etag"
    content_info.etag = "content_etag"


    # grab the page and make sure an etag comes back 
    res = app.get('/content.html')
    composite_etag = header_value(res.headers, 'etag')
    assert(composite_etag is not None and len(composite_etag) > 0)

    # check that deliverance gives 304 when the composite etag is given
    res = app.get('/content.html', headers={'If-None-Match': composite_etag})
    status = res.status
    assert(status == 304)

    theme_info.etag = 'something_else'
    # check that deliverance rebuilds when one of the etags changes 
    res = app.get('/content.html', headers={'If-None-Match': composite_etag})
    status = res.status
    # make sure the response etag changed 
    assert(header_value(res.headers, 'etag') != composite_etag)
    assert(status == 200)

    # clear etags 
    theme_info.etag = None
    rule_info.etag = None
    content_info.etag = None

    # make sure there is no more etag 
    res = app.get('/content.html')
    composite_etag = header_value(res.headers, 'etag')
    assert(composite_etag is None or len(composite_etag) == 0)

    # test modification dates 
    then = now() 
    theme_info.mod_time = then - 10 
    rule_info.mod_time = then - 20 
    content_info.mod_time = then - 30 
    
    res = app.get('/content.html')
    status = res.status
    assert(status == 200)

    res = app.get('/content.html', 
                  headers={'If-Modified-Since': formatdate(then)})
    status = res.status
    assert(status == 304)

    res = app.get('/content.html', 
                  headers={'If-Modified-Since': formatdate(then-60)})
    status = res.status
    assert(status == 200)

    res = app.get('/content.html', 
                  headers={'If-Modified-Since': formatdate(then-15)})
    status = res.status
    assert(status == 200)

def do_rule_uri_environ(renderer_type, name):
    from deliverance.utils import setRuleURI
    wsgi_app = DeliveranceMiddleware(urienv_app, 'theme.html', 'rules.xml',
                                     renderer_type)
    environ = {}
    setRuleURI(environ, 'rules2.xml')
    app = TestApp(wsgi_app, extra_environ=environ)
    res = app.get('/example.html')
    res2 = app.get('/example_expected_rule_uri_environ.html?notheme')
    html_string_compare(res.body, res2.body)

def do_theme_uri_environ(renderer_type, name):
    from deliverance.utils import setThemeURI
    wsgi_app = DeliveranceMiddleware(urienv_app, 'theme.html', 'rules.xml',
                                     renderer_type)
    environ = {}
    setThemeURI(environ, 'theme2.html')
    app = TestApp(wsgi_app, extra_environ=environ)
    res = app.get('/example.html')
    res2 = app.get('/example_expected_theme_uri_environ.html?notheme')
    html_string_compare(res.body, res2.body)
    
def do_serializer_environ(renderer_type, name):
    from deliverance.utils import setSerializer
    wsgi_app = DeliveranceMiddleware(urienv_app, 'theme.html', 'rules.xml',
                                     renderer_type)
    environ = {}
    setSerializer(environ, 'deliverance.test_wsgi:_uppercaseTextNodes')
    app = TestApp(wsgi_app, extra_environ=environ)
    res = app.get('/example.html')
    res2 = app.get('/example_expected_uppercase.html?notheme')
    html_string_compare(res.body, res2.body)


def _uppercaseTextNodes(content):
    from htmlserialize import tostring
    return tostring(content,
                    doctype_pair=("-//W3C//DTD HTML 4.01 Transitional//EN",
                                  "http://www.w3.org/TR/html4/loose.dtd")
                   ).upper()

RENDERER_TYPES = ['py', 'xslt']
TEST_FUNCS = [ do_url, do_basic, do_text, do_tasktracker, do_xinclude, do_with_spaces, do_nycsr, do_necoro, do_guidesearch, do_ajax, do_aggregate, do_aggregate2, do_cache, do_ignore, do_ignore_header, do_rule_uri_environ, do_theme_uri_environ, do_serializer_environ ] 

def test_all():
    for renderer_type in RENDERER_TYPES:
        for test_func in TEST_FUNCS: 
            yield test_func, renderer_type, test_func.func_name
            

if __name__ == '__main__':
    pass


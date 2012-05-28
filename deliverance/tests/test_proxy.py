import datetime
from deliverance.log import SavingLogger
from deliverance.proxy import Proxy
from deliverance.util.filetourl import filename_to_url
from lxml.etree import fromstring
from pkg_resources import resource_filename
from time import mktime
from webtest import TestApp, TestResponse, TestRequest
from webob import Request
from wsgiref.handlers import format_date_time

app = None
def setup():
    global app

    el = fromstring("""
<proxy path="/_theme">
  <dest href="{here}/test_content" />
</proxy>
""")

    here = resource_filename("deliverance", "tests/test_proxy.py")

    proxy = Proxy.parse_xml(el, filename_to_url(here))

    class FakeMiddleware(object):
        def link_to(*args, **kw):
            return "<url %s, %s>" % (args, kw)

    def wsgi_app(environ, start_response):
        middleware = FakeMiddleware()
        environ['deliverance.log'] = SavingLogger(Request(environ), middleware)
        return proxy.forward_request(environ, start_response)
    app = TestApp(wsgi_app)

def httpdate(dt):
    return format_date_time(mktime(dt.timetuple()))

def test_no_cache_theme_file():
    """
    http://www.coactivate.org/projects/deliverance/lists/deliverance-discussion/archive/2012/05/1337803417523
    """
    resp = app.get("/_theme/theme.html")
    assert resp.status == "200 OK"
    
    recently = datetime.datetime.now() - datetime.timedelta(1)
    recently = httpdate(recently)
    resp = app.get("/_theme/theme.html", extra_environ=dict(HTTP_IF_MODIFIED_SINCE=recently))
    assert resp.status == "200 OK", resp.status
    

from deliverance.log import PrintingLogger
from deliverance.middleware import DeliveranceMiddleware
from deliverance.middleware import FileRuleGetter, SubrequestRuleGetter
import logging
from lxml.cssselect import CSSSelector
import lxml.html
import re
from paste.urlmap import URLMap
import pkg_resources
import tempfile
from webob import Request, Response
from webtest import TestApp

def find_in_css(html, css, what):
    tree = lxml.html.document_fromstring(html)
    sel = CSSSelector(css)
    results = sel(tree)
    results = '\n'.join(lxml.html.tostring(r)
                        for r in results)

    regexp = re.compile(what, re.IGNORECASE)
    m = regexp.search(results)
    if not m:
        raise AssertionError("no match to '%s' in '%s'" %
                             (what, results))
    
    if m.groups():
        match_str = m.group(1)
    else:
        match_str = m.group(0)
    return match_str

def notfind_in_css(html, css, what):
    try:
        find_in_css(html, css, what)
    except AssertionError:
        return
    raise AssertionError("match to '%s' in %s" % (what, repr(css)))

def get_text(name):
    path = pkg_resources.resource_filename(
        "deliverance", "tests/test_content/%s" % name)
    try:
        fp = open(path)
        content = fp.read()
    finally:
        fp.close()
    return content

def make_response(*args, **kw):
    def f(environ, start_response):
        return Response(*args, **kw)(environ, start_response)
    return f

def setup_backend_site():
    app = URLMap()
    
    app['/theme.html'] = make_response(get_text("theme.html"))

    app['/blog/index.html'] = make_response(get_text("blog_index.html"))
    app['/about.html'] = make_response(get_text("about.html"))
    app['/magic'] = make_response(get_text("magic.html"), headerlist=[
            ('Content-Type', "text/html"), ('X-No-Deliverate', "1")])
    app['/magic2'] = make_response(get_text("magic2.html"))
    app['/foo'] = make_response(get_text("foo.html"))
    app['/empty'] = make_response("")
    app['/html_entities.html'] = make_response(get_text("html_entities.html"))

    rule_xml = get_text("rule.xml")
    # Rule files can be published and fetched with a subrequest:
    app['/mytheme/rules.xml'] = make_response(rule_xml, content_type="application/xml")

    # Rule files can also be read directly from the filesystem:
    rule_filename_pos, rule_filename = tempfile.mkstemp()
    f = open(rule_filename, 'w+')
    f.write(rule_xml)
    f.close()

    # We'll set up one DeliveranceMiddleware using the published rules, 
    # and another using the rule file:
    deliv_filename = DeliveranceMiddleware(
        app, FileRuleGetter(rule_filename),
        PrintingLogger, log_factory_kw=dict(print_level=logging.WARNING))
    deliv_url = DeliveranceMiddleware(
        app, SubrequestRuleGetter('http://localhost/mytheme/rules.xml'),
        PrintingLogger, log_factory_kw=dict(print_level=logging.WARNING))
    raw_app = TestApp(app)

    deliv_filename = TestApp(deliv_filename)
    deliv_url = TestApp(deliv_url)

    return deliv_filename, deliv_url, raw_app

def test_fundamentals():
    deliv_filename, deliv_url, raw_app = setup_backend_site()

    resp = raw_app.get("/blog/index.html")
    resp.mustcontain("A blog post")
    resp.mustcontain("footer that will be ignored")
    assert "2000 Some Corporation" not in resp

    resp = deliv_filename.get("/blog/index.html")
    resp.mustcontain("A blog post")
    assert "footer that will be ignored" not in resp
    resp.mustcontain("2000 Some Corporation")

    resp = deliv_url.get("/blog/index.html")
    resp.mustcontain("A blog post")
    assert "footer that will be ignored" not in resp
    resp.mustcontain("2000 Some Corporation")

    assert deliv_filename.get("/blog/index.html").body == \
        deliv_url.get("/blog/index.html").body

    resp = raw_app.get("/about.html")
    resp.mustcontain("all about this site.")
    notfind_in_css(resp.body, "div#content-wrapper", "all about this site.")
    find_in_css(resp.body, "title", "About this site")
    find_in_css(resp.body, "div#footer", "footer that will be ignored")
    
    resp = deliv_url.get("/about.html")
    resp.mustcontain("all about this site.")
    find_in_css(resp.body, "div#content-wrapper", "all about this site.")
    find_in_css(resp.body, "title", "About this site")
    # FIXME: why is this supposed to show up here?
    find_in_css(resp.body, "div#footer", "footer that will be ignored")

def test_x_no_deliverate_header():
    deliv_filename, deliv_url, raw_app = setup_backend_site()
    assert "2000 Some Corporation" not in deliv_url.get("/magic")
    assert deliv_filename.get("/magic").body == \
        deliv_url.get("/magic").body == raw_app.get("/magic").body

def test_x_no_deliverate_meta_tag():
    deliv_filename, deliv_url, raw_app = setup_backend_site()
    assert "2000 Some Corporation" not in deliv_url.get("/magic2")
    assert deliv_filename.get("/magic2").body == \
        deliv_url.get("/magic2").body == raw_app.get("/magic2").body
    
def test_empty_response():
    """ Deliverance should not blow up if the content response is empty """
    deliv_filename, deliv_url, raw_app = setup_backend_site()
    resp = deliv_url.get("/empty")
    assert resp.body == ''
    assert resp.status == "200 OK"

def test_html_entities():
    """ Deliverance should preserve HTML entities in content correctly """
    deliv_filename, deliv_url, raw_app = setup_backend_site()
    raw_app.get("/html_entities.html").mustcontain("&hellip;")
    deliv_url.get("/html_entities.html").mustcontain("&#8230;")


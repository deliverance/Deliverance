# -*- coding: utf-8 -*-
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
from webtest import TestApp, TestResponse, TestRequest

class HtmlTestResponse(TestResponse):
    def find_in_css(self, css, what, raw=False, should_fail=False):
        html = self.body

        tree = lxml.html.document_fromstring(html)
        sel = CSSSelector(css)
        results = sel(tree)
        results = '\n'.join(lxml.html.tostring(r)
                            for r in results)

        if raw:
            found = what in results
            if should_fail:
                if not found:
                    return True
                else:
                    raise AssertionError("bad match to '%s' in '%s'" &
                                         (what, results))
            if found:
                return what
            else:
                raise AssertionError("no match to '%s' in '%s'" % 
                                     (what, results))

        regexp = re.compile(what, re.IGNORECASE)
        m = regexp.search(results)

        if should_fail:
            if not m:
                return True
            else:
                raise AssertionError("bad match to '%s' in '%s'" % 
                                     (what, results))

        if not m:
            raise AssertionError("no match to '%s' in '%s'" %
                                 (what, results))
        
        if m.groups():
            match_str = m.group(1)
        else:
            match_str = m.group(0)
        return match_str

class HtmlTestRequest(TestRequest):
    ResponseClass = HtmlTestResponse

class HtmlTestApp(TestApp):
    RequestClass = HtmlTestRequest

def get_text(name):
    path = pkg_resources.resource_filename(
        "deliverance", "tests/test_content/%s" % name)
    fp = open(path)
    try:
        content = fp.read()
    finally:
        fp.close()
    return content

def make_response(*args, **kw):
    def f(environ, start_response):
        return Response(*args, **kw)(environ, start_response)
    return f

raw_app = rule_filename = deliv_filename = deliv_url = None
def setup():
    # Monkeypatch webtest TestRequest to inject our custom TestResponse
    # for now, hopefully subclass approach (demonstrated above to no effect)
    # will be merged to WebTest trunk (from bitbucket.org/ejucovy/webtest)
    TestRequest.ResponseClass = HtmlTestResponse

    global raw_app, rule_filename, deliv_filename, deliv_url
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
    app['/xhtml_doctype.html'] = make_response(get_text("xhtml_doctype.html"))
    app['/no_xhtml_doctype.html'] = make_response(get_text("no_xhtml_doctype.html"))
    app['/scriptcomments'] = make_response(get_text("scriptcomments.html"))
    app['/xhtml_scriptcomments'] = make_response(get_text("xhtml_scriptcomments.html"))

    app['/cdata.html'] = make_response(get_text("cdata.html"))
    app['/newfooter.html'] = make_response(get_text("newfooter.html"))
    app['/newfooter_sneaky_cdata.html'] = make_response(get_text("newfooter_sneaky_cdata.html"))

    app['/reddot.html'] = make_response(get_text("reddot.html"))
    app['/reddot2.html'] = make_response(get_text("reddot2.html"))
    app['/ellipse.html'] = make_response(get_text("ellipse.html"))

    app['/collapse_theme.html'] = make_response(get_text("collapse_theme.html"))
    app['/collapse_content.html'] = make_response(get_text("collapse_content.html"))

    rule_xml = get_text("rule.xml")

    # Rule files can be read directly from the filesystem:
    rule_filename_pos, rule_filename = tempfile.mkstemp()
    f = open(rule_filename, 'w+')
    f.write(rule_xml)
    f.close()

    # Rule files can also be published and fetched with an HTTP subrequest:
    def read_rule_file(environ, start_response):
        f = open(rule_filename)
        content = f.read()
        f.close()
        return Response(content, content_type="application/xml")(environ, start_response)
    app['/mytheme/rules.xml'] = read_rule_file

    # We'll set up one DeliveranceMiddleware using the published rules, 
    # and another using the rule file:
    deliv_filename = DeliveranceMiddleware(
        app, FileRuleGetter(rule_filename),
        PrintingLogger, log_factory_kw=dict(print_level=logging.WARNING))
    deliv_url = DeliveranceMiddleware(
        app, SubrequestRuleGetter('http://localhost/mytheme/rules.xml'),
        PrintingLogger, log_factory_kw=dict(print_level=logging.WARNING))
    raw_app = HtmlTestApp(app)

    deliv_filename = HtmlTestApp(deliv_filename)
    deliv_url = HtmlTestApp(deliv_url)

def teardown():
    TestRequest.ResponseClass = TestResponse

def test_fundamentals():
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
    resp.find_in_css("div#content-wrapper", "all about this site.", 
                     should_fail=True)
    resp.find_in_css("title", "About this site")
    resp.find_in_css("div#footer", "footer that will be ignored")
    
    resp = deliv_url.get("/about.html")
    resp.mustcontain("all about this site.")
    resp.find_in_css("div#content-wrapper", "all about this site.")
    resp.find_in_css("title", "About this site")
    # FIXME: why is this supposed to show up here?
    resp.find_in_css("div#footer", "footer that will be ignored")

def test_x_no_deliverate_header():
    assert "2000 Some Corporation" not in deliv_url.get("/magic")
    assert deliv_filename.get("/magic").body == \
        deliv_url.get("/magic").body == raw_app.get("/magic").body

def test_x_no_deliverate_meta_tag():
    assert "2000 Some Corporation" not in deliv_url.get("/magic2")
    assert deliv_filename.get("/magic2").body == \
        deliv_url.get("/magic2").body == raw_app.get("/magic2").body
    
def test_empty_response():
    """ Deliverance should not blow up if the content response is empty """
    resp = deliv_url.get("/empty")
    assert resp.body == ''
    assert resp.status == "200 OK"

def test_html_entities():
    """ Deliverance should preserve HTML entities in content correctly """
    raw_app.get("/html_entities.html").mustcontain("&hellip;")
    deliv_url.get("/html_entities.html").mustcontain("&#8230;")

def test_reread_filesystem_rule_file():

    # If you're using the SubrequestRuleGetter (a http:// url for the rule-doc)
    # then Deliverance will always reload the rule-doc on every request.
    # If you're using the FileRuleGetter (a file:// url for the rule-doc)
    # then Deliverance will only load the rule-doc once, and keep it in memory,
    # unless you set rule_getter.always_reload = True.

    resp = deliv_filename.get("/blog/index.html")
    url_resp = deliv_url.get("/blog/index.html")

    assert resp.body == url_resp.body

    new_rule_xml = get_text("new_rule.xml")
    f = open(rule_filename, 'w+')
    f.write(new_rule_xml)
    f.close()
    new_resp = deliv_filename.get("/blog/index.html")

    assert resp.body == new_resp.body

    url_resp = deliv_url.get("/blog/index.html")
    assert resp.body != url_resp.body

    deliv_filename.app.rule_getter.always_reload = True
    newer_resp = deliv_filename.get("/blog/index.html")
    assert new_resp.body != newer_resp.body

def test_xhtml_doctype():
    """ 
    The content's DOCTYPE should be respected. So if the content's DOCTYPE is XHTML,
    the merged output should preserve that DOCTYPE, and self-closing tags should be
    preserved rather than being rewritten as unclosed tags.
    """
    
    resp = deliv_url.get("/xhtml_doctype.html")
    resp.mustcontain('<img src="foo.png" />')
    # There's a new id="top" attribute on the <a name="top"> tag;
    # it's required for XHTML: http://www.w3.org/TR/xhtml1/#h-4.10
    resp.mustcontain('<a name="top" id="top">')
    assert "XHTML 1.0 Transitional//EN" in \
        lxml.html.fromstring(resp.body).getroottree().docinfo.doctype

    # Compare to the same content sans doctype declaration:
    resp = deliv_url.get("/no_xhtml_doctype.html")
    resp.mustcontain('<img src="foo.png">')
    resp.mustcontain('<a name="top">')
    assert "HTML 4.0 Transitional//EN" in \
        lxml.html.fromstring(resp.body).getroottree().docinfo.doctype

def test_rule_matches():
    # FIXME: what is this testing exactly?  look in rules.xml and also commit history
    raw_app.get("/foo").mustcontain("badstuff")
    assert "badstuff" not in deliv_url.get("/foo")

def test_style_comments_not_escaped():
    """ Test that HTML comments inside SCRIPT and STYLE tags aren't escaped """
    # FIXME: not working as a regex search; probably some special characters are in there
    deliv_url.get("/scriptcomments").find_in_css(
        "style",
        "<!-- @import url( http://localhost:8080/testplonesite/content_types.css); -->",
        raw=True)

    # But the same content with an XHTML doctype *will* escape
    # the HTML comments; they are not valid in XHTML
    # FIXME: link to reference in trac / mailing list archives
    deliv_url.get("/xhtml_scriptcomments").find_in_css(
        "style",
        "&lt;!-- @import url( http://localhost:8080/testplonesite/content_types.css); --&gt;",
        raw=True)
    
def test_cdata_preserved():
    """ 
    CDATA sections in XHTML documents should be preserved! lxml has a tendency to escape the angle brackets
    that start and end a CDATA section in XHTML documents (but not HTML) -- so Deliverance will munge the 
    markers that start and end CDATA sections before passing the documents to lxml, and then unmunge them
    after getting a merged string back from lxml. Let's make sure they're properly preserved in both theme
    and content documents.
    """
    # Swap out the theme-doc for one which has a cdata section:
    deliv_url.app.app['/theme.html'] = make_response(get_text("cdata_theme.html"))

    # Look for the CDATA section in the head provided by the theme-doc:
    raw_app.get("/cdata.html").find_in_css("head", "<![CDATA[",
                                           raw=True, should_fail=True)
    deliv_url.get("/cdata.html").find_in_css(
        "head", "/*<![CDATA[*/", raw=True)

    # And look for the CDATA section in the body provided by the content-doc:
    raw_app.get("/cdata.html").find_in_css(
        "body", "//<![CDATA[", raw=True)
    deliv_url.get("/cdata.html").find_in_css(
        "body", "//<![CDATA[", raw=True)

    # Make sure that the content within the CDATA section is properly unescaped:
    deliv_url.get("/cdata.html").find_in_css(
        "body script", "foo < bar", raw=True)
    deliv_url.get("/cdata.html").find_in_css(
        "body script", "foo &lt; bar", raw=True, should_fail=True)

    # We should also see what happens to CDATA sections merged in from external
    # content documents, when the `href` attribute  is used in a rule action.

    # First we'll swap in a new rule file that pulls in content from /newfooter.html
    new_rule_xml = get_text("rule_with_cdata_footer.xml")
    f = open(rule_filename, 'w+')
    f.write(new_rule_xml)
    f.close()

    # FIXME: why doesn't find_in_css work for this? lxml is eating the cdata
    # in the footer, but not the cdata elsewhere in the same document.
    assert """
    <div id="footer">
      foo
      <![CDATA[
                some unescaped script content in the footer
                ]]>
    </div>""" not in raw_app.get("/cdata.html")
    deliv_url.get("/cdata.html").mustcontain("""
    <div id="footer">
      foo
      <![CDATA[
                some unescaped script content in the footer
                ]]>
    </div>""")

    # Note that there's a small chance of false positives, if a document 
    # happens to contain the text markers that we use internally for the 
    # CDATA start and end.
    # (__START_CDATA__ and __END_CDATA__, defined in deliverance.utils.cdata)
    
    # Swap in yet another rule file, ho-hum
    new_rule_xml = get_text("rule_with_sneaky_cdata_footer.xml")
    f = open(rule_filename, 'w+')
    f.write(new_rule_xml)
    f.close()
    
    raw_app.get("/newfooter_sneaky_cdata.html").find_in_css(
        "#footer", "__START_CDATA__")
    assert "__START_CDATA__" not in deliv_url.get("/cdata.html")
    deliv_url.get("/cdata.html").mustcontain("""
    <div id="footer">
      foo
      <![CDATA[
                some unescaped script content in the footer
                ]]>
    </div>""")

def test_meta_charset_declaration():
    """
    lxml will properly parse html documents only if the meta tag with charset
    declaration occurs before any chars outside ASCII (per the HTML spec). To
    play nicely with content that breaks that assumption, Deliverance will move
    the charset declaration before passing the document to lxml, to make sure
    the resulting content isn't mangled.
    """
    # FIXME: find mailing list reference about this, whynot
    # FTR, they're called reddot b/c RedDot CMS does this, apparently
    raw_app.get("/reddot.html").mustcontain("日本語")
    deliv_url.get("/reddot.html").mustcontain(
        "日本語".decode("utf8").encode("ascii", "xmlcharrefreplace"))
    raw_app.get("/reddot2.html").mustcontain("日本語")
    deliv_url.get("/reddot2.html").mustcontain(
        "日本語".decode("utf8").encode("ascii", "xmlcharrefreplace"))

    raw_app.get("/reddot.html").mustcontain("""</title>
    <meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
  </head>""")
    deliv_url.get("/reddot.html").mustcontain(
        """<head><meta http-equiv="Content-Type" content="text/html; charset=UTF-8"><title>""")

    # reddot2.html has a closing meta-tag, which isn't correct for html.
    # we're just showing here that lxml will remove the closing tag.
    raw_app.get("/reddot2.html").mustcontain("""</title>
    <meta http-equiv="Content-Type" content="text/html; charset=UTF-8"></meta>
  </head>""")
    deliv_url.get("/reddot2.html").mustcontain(
        """<head><meta http-equiv="Content-Type" content="text/html; charset=UTF-8"><title>""")

    # Let's test that for the theme document also. We'll put the Japanese title and misplaced
    # charset declaration in the theme instead of the content. The resulting title should be
    # the correct HTML sequence:
    raw_app.app['/theme.html'] = make_response(get_text("new_theme.html"))
    resp = deliv_url.get("/foo")
    resp.find_in_css(
        "title", "日本語".decode("utf8").encode("ascii", "xmlcharrefreplace"),
        raw=True)
    raw_app.get("/theme.html").mustcontain("""</title>
    <meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
    <link""")
    resp.mustcontain("""<head><meta http-equiv="Content-Type" content="text/html; charset=UTF-8"><title>""")

def test_nonascii_characters():
    # Some non-ASCII characters can end up mangled when they pass through lxml.html
    ellipse = "…"
    x = "<html><body>%s</body></html>" % ellipse
    assert lxml.html.tostring(lxml.html.fromstring(x)) != \
        "<html><body>%s</body></html>" % ellipse.decode("utf8").encode("ascii", "xmlcharrefreplace")
   
    # That should have been "&#8230;", which is the HTML code for the ellipsis character.
    # The way to fix this is to decode the string to unicode before lxml.html gets it.
    assert lxml.html.tostring(lxml.html.fromstring(x.decode("utf"))) == \
        "<html><body>%s</body></html>" % ellipse.decode("utf8").encode("ascii", "xmlcharrefreplace")

    # So, internally, Deliverance will use webob.Response.unicode_body, which uses the
    # response's charset to figure out how to decode the string. Let's make sure that
    # these characters aren't mangled when they are themed through Deliverance::
    raw_app.get("/ellipse.html").mustcontain(ellipse)
    deliv_url.get("/ellipse.html").mustcontain(
        ellipse.decode("utf8").encode("ascii", "xmlcharrefreplace"))
    deliv_url.get("/ellipse.html").find_in_css(
        "body", ellipse.decode("utf8").encode("ascii", "xmlcharrefreplace"))

def test_source_tracking():
    # By default Deliverance keeps track of the source of elements in the
    # theme.  If content elements are merged into the theme, later actions
    # won't be able to find those elements in the theme.  

    # Swap in a new rule file to test this, ho hum
    f = open(rule_filename, 'w+')
    f.write(get_text("rule_test_source_tracking.xml"))
    f.close()

    # The <div>Content div!</div> from the content source will remain in the
    # output, since the <drop> action only applies to elements that were in
    # the original theme, even though that div has landed in the theme by
    # the time the <drop> action occurs::
    raw_app.get("/collapse_content.html").find_in_css(
        "body div", "Content div!")
    deliv_url.get("/collapse_content.html").find_in_css(
        "body div", "Content div!")

    # It is occasionally useful to tell Deliverance to ignore this
    # distinction and act on elements that were placed in the theme by an
    # earlier rule. To do this, use a ``<rule collapse-sources="1" />``. If
    # this attribute is set for an action, then elements that are moved into
    # the theme during that action will be immediately merged with the theme
    # so that later actions on the theme can act upon them.  So in our
    # example, setting ``collapse-sources="1"`` on the <append> action will
    # cause the final output to contain no <div>s at all::

    # Swap in a new rule file to test this .. ho hum
    f = open(rule_filename, 'w+')
    f.write(get_text("rule_test_source_collapsing.xml"))
    f.close()

    raw_app.get("/collapse_content.html").find_in_css(
        "body div", "Content div!")
    deliv_url.get("/collapse_content.html").find_in_css(
        "body div", "Content div!", should_fail=True)
    assert "div" not in deliv_url.get("/collapse_content.html")

def test_head_requests():
    """
    The proxy should be able to handle HEAD requests properly, meaning that
    the response headers (including Content-length) for a HEAD request should
    match the headers for a GET request through Deliverance -- and may not match
    the response headers for a request that circumvents Deliverance.
    """
    resp = raw_app.head("/collapse_content.html")
    raw_content_length = len(get_text("collapse_content.html"))
    assert not resp.body
    assert resp.content_length == raw_content_length

    head_resp = deliv_filename.head("/collapse_content.html")
    assert not head_resp.body
    assert head_resp.content_length != raw_content_length

    resp = deliv_filename.get("/collapse_content.html")
    assert resp.content_length == head_resp.content_length
    assert resp.headers == head_resp.headers

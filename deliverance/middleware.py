"""
Implements the middleware that does the Deliverance transformations.
"""

import posixpath
import mimetypes
import os
import urllib
import urlparse
import re
import simplejson
import datetime
from webob import Request, Response
from webob import exc
from wsgiproxy.exactproxy import proxy_exact_request
from pygments import highlight as pygments_highlight
from pygments.lexers import XmlLexer, HtmlLexer
from pygments.formatters import HtmlFormatter
from tempita import HTMLTemplate, html
from lxml.etree import _Element, XMLSyntaxError
from lxml.html import fromstring, document_fromstring, tostring, Element
from deliverance.log import SavingLogger
from deliverance.security import display_logging, display_local_files, edit_local_files
from deliverance.util.filetourl import url_to_filename
from deliverance.editor.editorapp import Editor
from deliverance.rules import clientside_action
from deliverance.ruleset import RuleSet


__all__ = ['DeliveranceMiddleware', 'RulesetGetter', 'SubrequestRuleGetter',
           'FileRuleGetter', 'make_deliverance_middleware' ]


class DeliveranceMiddleware(object):
    """
    The middleware that implements the Deliverance transformations
    """

    ## FIXME: is log_factory etc very useful?
    def __init__(self, app, rule_getter, log_factory=SavingLogger, 
                 log_factory_kw={}, default_theme=None):
        self.app = app
        self.rule_getter = rule_getter
        self.log_factory = log_factory
        self.log_factory_kw = log_factory_kw

        self.default_theme = default_theme

        ## FIXME: clearly, this should not be a dictionary:
        self.known_html = set()
        self.known_titles = {}

    def log_description(self, log=None):
        """The description shown in the log for this context"""
        return 'Deliverance'

    def __call__(self, environ, start_response):
        req = Request(environ)
        if 'deliv_notheme' in req.GET:
            return self.app(environ, start_response)
        req.environ['deliverance.base_url'] = req.application_url
        ## FIXME: copy_get?:
        orig_req = Request(environ.copy())
        if 'deliverance.log' in req.environ:
            log = req.environ['deliverance.log']
        else:
            log = self.log_factory(req, self, **self.log_factory_kw)
            ## FIXME: should this be put in both the orig_req and this req?
            req.environ['deliverance.log'] = log
        def resource_fetcher(url, retry_inner_if_not_200=False):
            """
            Return the Response object for the given URL
            """
            return self.get_resource(url, orig_req, log, retry_inner_if_not_200)
        if req.path_info_peek() == '.deliverance':
            req.path_info_pop()
            resp = self.internal_app(req, resource_fetcher)
            return resp(environ, start_response)
        rule_set = self.rule_getter(resource_fetcher, self.app, orig_req)
        clientside = rule_set.check_clientside(req, log)
        if clientside and req.url in self.known_html:
            if req.cookies.get('jsEnabled'):
                log.debug(self, 'Responding to %s with a clientside theme' % req.url)
                return self.clientside_response(req, rule_set, resource_fetcher, log)(environ, start_response)
            else:
                log.debug(self, 'Not doing clientside theming because jsEnabled cookie not set')
        resp = req.get_response(self.app)
        ## FIXME: also XHTML?
        if resp.content_type != 'text/html':
            ## FIXME: remove from known_html?
            return resp(environ, start_response)
        
        # XXX: Not clear why such responses would have a content type, but
        # they sometimes do (from Zope/Plone, at least) and that then breaks
        # when trying to apply a theme.
        if resp.status_int in (301, 302, 304):
            return resp(environ, start_response)
            
        if resp.content_length == 0:
            return resp(environ, start_response)

        if clientside and req.url not in self.known_html:
            log.debug(self, '%s would have been a clientside check; in future will be since we know it is HTML'
                      % req.url)
            self.known_titles[req.url] = self._get_title(resp.body)
            self.known_html.add(req.url)
        resp = rule_set.apply_rules(req, resp, resource_fetcher, log, 
                                    default_theme=self.default_theme)
        if clientside:
            resp.decode_content()
            resp.body = self._substitute_jsenable(resp.body)
        resp = log.finish_request(req, resp)

        return resp(environ, start_response)

    _title_re = re.compile(r'<title>(.*?)</title>', re.I|re.S)

    def _get_title(self, body):
        match = self._title_re.search(body)
        if match:
            return match.group(1)
        else:
            return None

    _end_head_re = re.compile(r'</head>', re.I)
    _jsenable_js = '''\
<script type="text/javascript">
document.cookie = 'jsEnabled=1; expires=__DATE__; path=/';
</script>'''
    _future_date = (datetime.datetime.now() + datetime.timedelta(days=10*365)).strftime('%a, %d-%b-%Y %H:%M:%S GMT')

    def _substitute_jsenable(self, body):
        match = self._end_head_re.search(body)
        if not match:
            return body
        js = self._jsenable_js.replace('__DATE__', self._future_date)
        return body[:match.start()] + js + body[match.start():]

    def clientside_response(self, req, rule_set, resource_fetcher, log):
        theme_href = rule_set.default_theme.resolve_href(req, None, log)
        theme_doc = rule_set.get_theme(theme_href, resource_fetcher, log)
        js = CLIENTSIDE_JAVASCRIPT.replace('__DELIVERANCE_URL__', req.application_url)
        theme_doc.head.insert(0, fromstring('''\
<script type="text/javascript">
%s
</script>''' % js))
        theme = tostring(theme_doc)
        ## FIXME: cache this, use the actual subresponse to get proper last-modified, etc
        title = self.known_titles.get(req.url)
        if title:
            theme = self._title_re.sub('<title>%s</title>' % title, theme)
        resp = Response(theme, conditional_response=True)
        if not resp.etag:
            resp.md5_etag()
        return resp

    def get_resource(self, url, orig_req, log, retry_inner_if_not_200=False):
        """
        Gets the resource at the given url, using the original request
        `orig_req` as the basis for constructing the subrequest.
        Returns a `webob.Response` object.

        If `url.startswith(orig_req.application_url + '/')`, then Deliverance
        will try to fetch the resource by making a subrequest to the app that
        is being wrapped by Deliverance, instead of an external subrequest.

        This can cause problems in some setups -- see #16. To work around
        this, if `retry_inner_if_not_200` is True, then, in the situation
        described above, non-200 responses from the inner app will be tossed
        out, and the request will be retried as an external http request.
        Currently this is used only by RuleSet.get_theme
        """
        assert url is not None
        if url.lower().startswith('file:'):
            if not display_local_files(orig_req):
                ## FIXME: not sure if this applies generally; some
                ## calls to get_resource might be because of a more
                ## valid subrequest than displaying a file
                return exc.HTTPForbidden(
                    "You cannot access file: URLs (like %r)" % url)
            filename = url_to_filename(url)
            if not os.path.exists(filename):
                return exc.HTTPNotFound(
                    "The file %r was not found" % filename)
            if os.path.isdir(filename):
                return exc.HTTPForbidden(
                    "You cannot display a directory (%r)" % filename)
            subresp = Response()
            type, dummy = mimetypes.guess_type(filename)
            if not type:
                type = 'application/octet-stream'
            subresp.content_type = type
            ## FIXME: reading the whole thing obviously ain't great:
            f = open(filename, 'rb')
            subresp.body = f.read()
            f.close()
            return subresp

        elif url.startswith(orig_req.application_url + '/'):
            subreq = orig_req.copy_get()
            subreq.environ['deliverance.subrequest_original_environ'] = orig_req.environ
            new_path_info = url[len(orig_req.application_url):]
            query_string = ''
            if '?' in new_path_info:
                new_path_info, query_string = new_path_info.split('?')
            new_path_info = urllib.unquote(new_path_info)
            assert new_path_info.startswith('/')
            subreq.path_info = new_path_info
            subreq.query_string = query_string
            subresp = subreq.get_response(self.app)
            ## FIXME: error if not HTML?
            ## FIXME: handle redirects?
            ## FIXME: handle non-200?
            log.debug(self, 'Internal request for %s: %s content-type: %s',
                            url, subresp.status, subresp.content_type)

            if not retry_inner_if_not_200:
                return subresp

            if subresp.status_int == 200:
                return subresp
            elif 'x-deliverance-theme-subrequest' in orig_req.headers:
                log.debug(self, 
                          'Internal request for %s was not 200 OK; '
                          'returning it anyway.' % url)
                return subresp
            else:
                log.debug(self,
                          'Internal request for %s was not 200 OK; retrying as external request.' % url)
            
        ## FIXME: pluggable subrequest handler?
        subreq = Request.blank(url)
        subreq.headers['x-deliverance-theme-subrequest'] = "1"
        subresp = subreq.get_response(proxy_exact_request)
        log.debug(self, 'External request for %s: %s content-type: %s',
                  url, subresp.status, subresp.content_type)
        return subresp

    def link_to(self, req, url, source=False, line=None, selector=None, 
                browse=False):
        """
        Creates a link to the given url for debugging purposes.

        ``source=True``: 
            link to the highlighted source for the file.

        ``line=#``:
            link to the specific line number

        ``selector="css/xpath"``: 
            highlight the element that matches that css/xpath selector

        ``browse=True``:
            link to a display that lets you see ids and classes in the
            document
        """
        base = req.environ['deliverance.base_url']
        base += '/.deliverance/view'
        source = int(bool(source))
        args = {'url': url}
        if source:
            args['source'] = '1'
        if line:
            args['line'] = str(line)
        if selector:
            args['selector'] = selector
        if browse:
            args['browse'] = '1'
        url = base + '?' + urllib.urlencode(args)
        if selector:
            url += '#deliverance-selection'
        if line:
            url += '#code-%s' % line
        return url

    def internal_app(self, req, resource_fetcher):
        """
        Handles all internal (``/.deliverance``) requests.
        """
        segment = req.path_info_peek()
        method = 'action_%s' % segment
        method = getattr(self, method, None)
        if not display_logging(req) and not getattr(method, 'exposed', False):
            return exc.HTTPForbidden(
                "Logging is not enabled for you")
        req.path_info_pop()
        if not method:
            return exc.HTTPNotFound('There is no %r action' % segment)
        try:
            return method(req, resource_fetcher)
        except exc.HTTPException, e:
            return e

    def action_media(self, req, resource_fetcher):
        """
        Serves up media from the ``deliverance/media`` directory.
        """
        ## FIXME: I'm not using this currently, because the Javascript
        ## didn't work.  Dunno why.
        from paste.urlparser import StaticURLParser
        app = StaticURLParser(os.path.join(os.path.dirname(__file__), 'media'))
        ## FIXME: need to pop some segments from the req?
        req.path_info_pop()
        resp = req.get_response(app)
        if resp.content_type == 'application/x-javascript':
            resp.content_type = 'application/javascript'
        return resp

    def action_view(self, req, resource_fetcher):
        """
        Views files; ``.link_to()`` creates links that go to this
        method.
        """
        url = req.GET['url']
        source = int(req.GET.get('source', '0'))
        browse = int(req.GET.get('browse', '0'))
        selector = req.GET.get('selector', '')
        subresp = resource_fetcher(url)
        if source:
            return self.view_source(req, subresp, url)
        elif browse:
            return self.view_browse(req, subresp, url)
        elif selector:
            return self.view_selection(req, subresp, url)
        else:
            return exc.HTTPBadRequest(
                "You must have a query variable source, browse, or selector")

    def action_edit_rules(self, req, resource_fetcher):
        if not edit_local_files(req.environ):
            return exc.HTTPForbidden('Editing is forbidden')
        rules = self.rule_getter(resource_fetcher, self.app, req)
        file_url = rules.source_location
        if not file_url.startswith('file:'):
            return exc.HTTPForbidden('The rule location (%s) is not a local file' % file_url)
        filename = url_to_filename(file_url)
        app = Editor(filename=filename, force_syntax='delivxml', title='rule file %s' % os.path.basename(filename))
        return app

    def view_source(self, req, resp, url):
        """
        View the highlighted source (from `action_view`).
        """
        content_type = resp.content_type
        if content_type.startswith('application/xml'):
            lexer = XmlLexer()
        elif content_type == 'text/html':
            lexer = HtmlLexer()
        else:
            ## FIXME: what then?
            lexer = HtmlLexer()
        text = pygments_highlight(
            resp.body, lexer,
            HtmlFormatter(full=True, linenos=True, lineanchors='code'))
        return Response(text)

    def view_browse(self, req, resp, url):
        """
        View the id/class browser (from `action_view`)
        """
        import re
        body = resp.body
        f = open(os.path.join(os.path.dirname(__file__), 'media', 'browser.js'))
        content = f.read()
        f.close()
        extra_head = '''
        <!-- Added by Deliverance for browsing: -->
        <script src="http://www.google.com/jsapi"></script>
        <script>
        %s
        </script>
        <style type="text/css">
          .deliverance-highlight {
            border: 5px dotted #f00;
          }
        </style>
        <base href="%s">
        <!-- Begin original page -->
        ''' % (
            content, posixpath.dirname(req.GET['url']) + '/')
        match = re.search(r'<head>', body, re.I)
        if match:
            body = body[:match.end()] + extra_head + body[match.end():]
        else:
            body = extra_head + body
        extra_body = '''
        <div style="display: block; color: #000; background-color: #dfd; font-family: sans-serif; font-size: 100%; border-bottom: 2px dotted #f00" id="deliverance-browser">
        <span style="float: right"><button onclick="window.close()">close</button></span>
        View by id/class: <select onchange="deliveranceChangeId()" name="deliverance-ids" id="deliverance-ids"></select>
        </div>'''
        match = re.search('<body.*?>', body, re.I)
        if match:
            body = body[:match.end()] + extra_body + body[match.end():]
        else:
            body = extra_body + body
        return Response(body)

    def view_selection(self, req, resp, url):
        """
        View the highlighted selector (from `action_view`)
        """
        from deliverance.selector import Selector
        doc = document_fromstring(resp.body)
        el = Element('base')
        el.set('href', posixpath.dirname(url) + '/')
        doc.head.insert(0, el)
        selector = Selector.parse(req.GET['selector'])
        dummy_type, elements, dummy_attributes = selector(doc)
        if not elements:
            template = self._not_found_template
        else:
            template = self._found_template
        all_elements = []
        els_in_head = False
        for index, el in enumerate(elements):
            el_in_head = self._el_in_head(el)
            if el_in_head:
                els_in_head = True
            anchor = 'deliverance-selection'
            if index:
                anchor += '-%s' % index
            if el.get('id'):
                anchor = el.get('id')
            ## FIXME: is a <a name> better?
            if not el_in_head:
                el.set('id', anchor)
            else:
                anchor = None
            ## FIXME: add :target CSS rule
            ## FIXME: or better, some Javascript
            all_elements.append((anchor, el))
            if not el_in_head:
                style = el.get('style', '')
                if style:
                    style += '; '
                style += '/* deliverance */ border: 2px dotted #f00'
                el.set('style', style)
            else:
                el.set('DELIVERANCE-MATCH', '1')
        def highlight(html_code):
            """Highlights the given code (for use in the template)"""
            if isinstance(html_code, _Element):
                html_code = tostring(html_code)
            return html(pygments_highlight(html_code, HtmlLexer(),
                                           HtmlFormatter(noclasses=True)))
        def format_tag(tag):
            """Highlights the lxml HTML tag"""
            return highlight(tostring(tag).split('>')[0]+'>')
        def wrap_html(html, width=100):
            if isinstance(html, _Element):
                html = tostring(html)
            lines = html.splitlines()
            new_lines = []
            def wrap_html_line(line):
                if len(line) <= width:
                    return [line]
                match_trail = re.search(r'^[^<]*</.*?>', line, re.S)
                if match_trail:
                    result = [match_trail.group(0)]
                    result.extend(wrap_html_line(line[match_trail.end():]))
                    return result
                match1 = re.search(r'^[^<]*<[^>]*>', line, re.S)
                match2 = re.search(r'<[^>]*>[^<>]*$', line, re.S)
                if not match1 or not match2:
                    return [line]
                result = [match1.group(0)]
                result.extend(wrap_html_line(line[match1.end():match2.start()]))
                result.append(match2.group(0))
                return result
            for line in lines:
                new_lines.extend(wrap_html_line(line))
            return '\n'.join(new_lines)
        def mark_deliv_match(highlighted_text):
            result = re.sub(r'(?:<[^/][^>]*>)*&lt;.*?DELIVERANCE-MATCH=.*?&gt;(?:</[^>]*>)*', lambda match: r'<b style="background-color: #ff8">%s</b>' % match.group(0), unicode(highlighted_text), re.S)
            return html(result)
        text = template.substitute(
            base_url=url,
            els_in_head=els_in_head, doc=doc,
            elements=all_elements, selector=selector, 
            format_tag=format_tag, highlight=highlight, 
            wrap_html=wrap_html, mark_deliv_match=mark_deliv_match)
        message = fromstring(
            self._message_template.substitute(message=text, url=url))
        if doc.body.text:
            message.tail = doc.body.text
            doc.body.text = ''
        doc.body.insert(0, message)
        text = tostring(doc)
        return Response(text)


    def _el_in_head(self, el):
        """True if the given element is in the HTML ``<head>``"""
        while el is not None:
            if el.tag == 'head':
                return True
            el = el.getparent()
        return False

    _not_found_template = HTMLTemplate('''\
    There were no elements that matched the selector <code>{{selector}}</code>
    ''', 'deliverance.middleware.DeliveranceMiddleware._not_found_template')

    _found_template = HTMLTemplate('''\
    {{if len(elements) == 1}}
      One element matched the selector <code>{{selector}}</code>;
      {{if elements[0][0]}}
        <a href="{{base_url}}#{{elements[0][0]}}">jump to element</a>
      {{else}}
        element is in head: {{highlight(elements[0][1])}}
      {{endif}}
    {{else}}
      {{len(elements)}} elements matched the selector <code>{{selector}}</code>:
      <ol>
      {{for anchor, el in elements}}
        {{if anchor}}
          <li><a href="{{base_url}}#{{anchor}}"><code>{{format_tag(el)}}</code></a></li>
        {{else}}
          <li>{{format_tag(el)}}</li>
        {{endif}}
      {{endfor}}
      </ol>
    {{endif}}
    {{if els_in_head}}
      <div style="border-top: 2px solid #000">
        <b>Elements matched in head.  Showing head:</b><br>
        <div style="margin: 1em; padding: 0.25em; background-color: #fff">
        {{mark_deliv_match(highlight(wrap_html(doc.head)))}}
        </div>
      </div>
    {{endif}}
    ''', 'deliverance.middleware.DeliveranceMiddleware._found_template')

    _message_template = HTMLTemplate('''\
    <div style="color: #000; background-color: #f90; border-bottom: 2px dotted #f00; padding: 1em">
    <span style="float: right; font-size: 65%"><button onclick="window.close()">close</button></span>
    Viewing <code><a style="text-decoration: none" href="{{url}}">{{url}}</a></code><br>
    {{message|html}}
    </div>''', 'deliverance.middleware.DeliveranceMiddleware._message_template')

    def action_subreq(self, req, resource_fetcher):
        log = req.environ['deliverance.log']
        from deliverance.log import PrintingLogger
        log = PrintingLogger(log.request, log.middleware)
        req.environ['deliverance.log'] = log
        url = req.GET['url']
        subreq = req.copy_get()
        base = req.environ['deliverance.base_url']
        assert url.startswith(base), 'Expected url %r to start with %r' % (url, base)
        rest = '/' + url[len(base):].lstrip('/')
        if '?' in rest:
            rest, qs = rest.split('?', 1)
        else:
            qs = ''
        subreq.script_name = urlparse.urlsplit(base)[2]
        subreq.path_info = rest
        subreq.query_string = qs
        resp = subreq.get_response(self.app)
        if resp.status_int == 304:
            return resp
        if resp.status_int != 200:
            assert 0, 'Failed response to request %s: %s' % (subreq.url, resp.status)
        assert resp.content_type == 'text/html', (
            'Unexpected content-type: %s (for url %s)' 
            % (resp.content_type, subreq.url))
        doc = fromstring(resp.body)
        if req.GET.get('action'):
            action = clientside_action(
                req.GET['action'], content_selector=req.GET['content'],
                theme_selector=req.GET['theme'])
            actions = action.clientside_actions(doc, log)
        else:
            rule_set = self.rule_getter(resource_fetcher, self.app, req)
            actions = rule_set.clientside_actions(subreq, resp, log)
        resp.body = simplejson.dumps(actions)
        resp.content_type = 'application/json'
        return resp

    action_subreq.exposed = True

fp = open(os.path.join(os.path.dirname(__file__), 'media', 'clientside.js'))
CLIENTSIDE_JAVASCRIPT = fp.read()
del fp

from lxml.etree import XML
import urlparse

class SubrequestRuleGetter(object):
    """
    An implementation of `rule_getter` for `DeliveranceMiddleware`.
    This retrieves and instantiates the rules using a subrequest with
    the given url.
    """

    _response = None
    
    def __init__(self, url):
        self.url = url
        
    def __call__(self, get_resource, app, orig_req):
        url = urlparse.urljoin(orig_req.url, self.url)
        doc_resp = get_resource(url)
        if doc_resp.status_int == 304 and self._response is not None:
            doc_resp = self._response
        elif doc_resp.status_int == 200:
            self._response = doc_resp
        else:
            ## FIXME: better error
            assert 0, "Bad response: %r" % doc_resp
        ## FIXME: better content-type detection
        if doc_resp.content_type not in ('application/xml', 'text/xml',):
            ## FIXME: better error
            assert 0, "Bad response content-type: %s (from response %r)" % (
                doc_resp.content_type, doc_resp)
        doc_text = doc_resp.body
        try:
            doc = XML(doc_text, base_url=url)
        except XMLSyntaxError, e:
            raise Exception('Invalid syntax in %s: %s' % (url, e))
        assert doc.tag == 'ruleset', (
            'Bad rule tag <%s> in document %s' % (doc.tag, url))
        return RuleSet.parse_xml(doc, url)

from lxml.etree import parse
class FileRuleGetter(object):
    """
    An implementation of `rule_getter` for `DeliveranceMiddleware`.
    This reads the rules from a file.

    If always_reload=True, the file will be re-read on every request.
    """

    def load_rules(self):
        filename = self.filename

        try:
            fp = open(filename)
            doc = parse(fp, base_url='file://'+os.path.abspath(filename)).getroot()
            fp.close()
        except XMLSyntaxError, e:
            raise Exception('Invalid syntax in %s: %s' % (filename, e))
        assert doc.tag == 'ruleset', (
            'Bad rule tag <%s> in document %s' % (doc.tag, filename))
        assert doc.tag == 'ruleset', (
            'Bad rule tag <%s> in document %s' % (doc.tag, filename))
        self.ruleset = RuleSet.parse_xml(doc, filename)
        
    def __init__(self, filename, always_reload=False):
        self.filename = filename
        self.always_reload = always_reload
        self.load_rules()

    def __call__(self, get_resource, app, orig_req):
        if self.always_reload:
            self.load_rules()
        return self.ruleset

from deliverance import security
from paste.deploy.converters import asbool

def make_deliverance_middleware(app, global_conf,
                                rule_uri=None, rule_filename=None,
                                theme_uri=None,
                                debug=None,
                                execute_pyref=None):

    assert sum([bool(x) for x in [rule_uri, rule_filename]]) == 1, (
        "You must give one, and only one, of rule_uri or rule_filename")

    if debug is None:
        debug = asbool(global_conf.get('debug', False))
    else:
        debug = asbool(debug)
    
    if rule_filename:
        rule_getter = FileRuleGetter(rule_filename, always_reload=debug)
    elif rule_uri.startswith('file://'):
        rule_uri = rule_uri[len('file://'):]
        rule_getter = FileRuleGetter(rule_uri, always_reload=debug)
    else:
        rule_getter = SubrequestRuleGetter(rule_uri)
    
    execute_pyref = asbool(execute_pyref)

    app = DeliveranceMiddleware(app, rule_getter, default_theme=theme_uri)

    app = security.SecurityContext.middleware(
        app,
        display_local_files=debug, display_logging=debug,
        execute_pyref=execute_pyref)
    
    return app

if __name__ == '__main__':
    import doctest
    doctest.testfile('tests/test_middleware.txt')


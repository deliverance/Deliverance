from webob import Request, Response
from webob import exc
from wsgiproxy.exactproxy import proxy_exact_request
from deliverance.log import SavingLogger
from deliverance.security import display_logging, display_local_files
from deliverance.util.filetourl import url_to_filename
import urllib
import hmac
import sha
from pygments import highlight as pygments_highlight
from pygments.lexers import XmlLexer, HtmlLexer, guess_lexer_for_filename
from pygments.formatters import HtmlFormatter
from tempita import HTMLTemplate, html_quote, html
from lxml.etree import _Element
from lxml.html import fromstring, document_fromstring, tostring, Element
import posixpath
import mimetypes
import os

class DeliveranceMiddleware(object):

    ## FIXME: is log_factory etc very useful?
    def __init__(self, app, rule_getter, log_factory=SavingLogger, log_factory_kw={}):
        self.app = app
        self.rule_getter = rule_getter
        self.log_factory = log_factory
        self.log_factory_kw = log_factory_kw

    def log_description(self, log=None):
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
        def resource_fetcher(url):
            return self.get_resource(url, orig_req, log)
        if req.path_info_peek() == '.deliverance':
            req.path_info_pop()
            resp = self.internal_app(req, resource_fetcher)
            return resp(environ, start_response)
        resp = req.get_response(self.app)
        ## FIXME: also XHTML?
        if resp.content_type != 'text/html':
            return resp(environ, start_response)
        rule_set = self.rule_getter(resource_fetcher, self.app, orig_req)
        resp = rule_set.apply_rules(req, resp, resource_fetcher, log)
        resp = log.finish_request(req, resp)
        return resp(environ, start_response)

    def get_resource(self, url, orig_req, log):
        assert url is not None
        if url.lower().startswith('file:'):
            if not display_local_files(orig_req):
                ## FIXME: not sure if this applies generally; some calls to get_resource might
                ## be because of a more valid subrequest than displaying a file
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
            type, encoding = mimetypes.guess_type(filename)
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
            return subresp
        else:
            ## FIXME: pluggable subrequest handler?
            subreq = Request.blank(url)
            subresp = subreq.get_response(proxy_exact_request)
            log.debug(self, 'External request for %s: %s content-type: %s',
                      url, subresp.status, subresp.content_type)
            return subresp

    def link_to(self, req, url, source=False, line=None, selector=None, browse=False):
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
        if not display_logging(req):
            return exc.HTTPForbidden(
                "Logging is not enabled for you")
        segment = req.path_info_peek()
        method = 'action_%s' % segment
        method = getattr(self, method, None)
        if not method:
            return exc.HTTPNotFound('There is no %r action' % segment)
        try:
            return method(req, resource_fetcher)
        except exc.HTTPException, e:
            return e

    def action_media(self, req, resource_fetcher):
        ## FIXME: I'm not using this currently, because the Javascript didn't work.  Dunno why.
        from paste.urlparser import StaticURLParser
        app = StaticURLParser(os.path.join(os.path.dirname(__file__), 'media'))
        ## FIXME: need to pop some segments from the req?
        req.path_info_pop()
        resp = req.get_response(app)
        if resp.content_type == 'application/x-javascript':
            resp.content_type = 'application/javascript'
        return resp

    def action_view(self, req, resource_fetcher):
        url = req.GET['url']
        source = int(req.GET.get('source', '0'))
        browse = int(req.GET.get('browse', '0'))
        line = int(req.GET.get('line', '0')) or ''
        selector = req.GET.get('selector', '')
        subresp = resource_fetcher(url)
        if source:
            return self.view_source(req, subresp)
        elif browse:
            return self.view_browse(req, subresp)
        else:
            return self.view_selection(req, subresp)

    def view_source(self, req, resp):
        ct = resp.content_type
        if ct.startswith('application/xml'):
            lexer = XmlLexer()
        elif ct == 'text/html':
            lexer = HtmlLexer()
        else:
            ## FIXME: what then?
            lexer = HtmlLexer()
        text = pygments_highlight(
            resp.body, lexer,
            HtmlFormatter(full=True, linenos=True, lineanchors='code'))
        return Response(text)

    def view_browse(self, req, resp):
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
            border: 2px dotted #f00;
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

    def view_selection(self, req, resp):
        from deliverance.selector import Selector
        doc = document_fromstring(resp.body)
        el = Element('base')
        el.set('href', posixpath.dirname(req.GET['url']) + '/')
        doc.head.insert(0, el)
        selector = Selector.parse(selector)
        type, elements, attributes = selector(doc)
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
            if isinstance(html_code, _Element):
                html_code = tostring(html_code)
            return html(pygments_highlight(html_code, HtmlLexer(),
                                           HtmlFormatter(noclasses=True)))
        def format_tag(tag):
            return highlight(tostring(tag).split('>')[0]+'>')
        text = template.substitute(
            base_url=req.url,
            els_in_head=els_in_head, doc=doc,
            elements=all_elements, selector=selector, 
            format_tag=format_tag, highlight=highlight)
        message = fromstring(self._message_template.substitute(message=text, url=url))
        if doc.body.text:
            message.tail = doc.body.text
            doc.body.text = ''
        doc.body.insert(0, message)
        text = tostring(doc)
        return Response(text)


    def _el_in_head(self, el):
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
        {{highlight(doc.head)}}
        </div>
      </div>
    {{endif}}
    ''', 'deliverance.middleware.DeliveranceMiddleware._found_template')

    _message_template = HTMLTemplate('''\
    <div style="color: #000; background-color: #f90; border-bottom: 2px dotted #f00">
    <span style="float: right; font-size: 65%"><button onclick="window.close()">close</button></span>
    Viewing <code><a style="text-decoration: none" href="{{url}}">{{url}}</a></code><br>
    {{message|html}}
    </div>''', 'deliverance.middleware.DeliveranceMiddleware._message_template')


class SubrequestRuleGetter(object):

    def __init__(self, url):
        self.url = url
    def __call__(self, get_resource, app, orig_req):
        from deliverance.ruleset import RuleSet
        from lxml.etree import XML, XMLSyntaxError
        import urlparse
        url = urlparse.urljoin(orig_req.url, self.url)
        doc_resp = get_resource(url)
        if doc_resp.status_int != 200:
            ## FIXME: better error
            assert 0, "Bad response: %r" % doc_resp
        ## FIXME: better content-type detection
        if doc_resp.content_type != 'application/xml':
            ## FIXME: better error
            assert 0, "Bad response content-type: %s (from response %r)" % (
                doc_resp.content_type, doc_resp)
        doc_text = doc_resp.body
        try:
            doc = XML(doc_text, base_url=url)
        except XMLSyntaxError, e:
            raise 'Invalid syntax in %s: %s' % (url, e)
        assert doc.tag == 'ruleset', 'Bad rule tag <%s> in document %s' % (doc.tag, url)
        return RuleSet.parse_xml(doc, url)

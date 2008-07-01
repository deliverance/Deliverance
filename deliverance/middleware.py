from webob import Request, Response
from webob import exc
from wsgiproxy.exactproxy import proxy_exact_request
from deliverance.log import SavingLogger
import urllib
import hmac
import sha
from pygments import highlight as pygments_highlight
from pygments.lexers import XmlLexer, HtmlLexer, guess_lexer_for_filename
from pygments.formatters import HtmlFormatter
from tempita import HTMLTemplate, html_quote, html
from lxml.etree import _Element
from lxml.html import fromstring, document_fromstring, tostring

class DeliveranceMiddleware(object):

    def __init__(self, app, rule_getter, log_factory=SavingLogger, log_factory_kw={}):
        self.app = app
        self.rule_getter = rule_getter
        self.log_factory = log_factory
        self.log_factory_kw = log_factory_kw

    def log_description(self, log=None):
        return 'Deliverance'

    def __call__(self, environ, start_response):
        ## FIXME: copy_get?:
        req = Request(environ)
        req.environ['deliverance.base_url'] = req.application_url
        orig_req = Request(environ.copy())
        log = self.log_factory(req, self, **self.log_factory_kw)
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
        ## FIXME: should this return a webob.Response object?
        if url.startswith(orig_req.application_url + '/'):
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
            resp = subreq.get_response(proxy_exact_request)
            log.debug(self, 'External request for %s: %s content-type: %s',
                      url, subresp.status, subresp.content_type)
            return subresp


    def link_to(self, req, url, source=False, line=None, selector=None):
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
        url = base + '?' + urllib.urlencode(args)
        if selector:
            url += '#deliverance-selection'
        if line:
            url += '#code-%s' % line
        return url

    def internal_app(self, req, resource_fetcher):
        segment = req.path_info_peek()
        method = 'action_%s' % segment
        method = getattr(self, method, None)
        if not method:
            return exc.HTTPNotFound('There is no %r action' % segment)
        try:
            return method(req, resource_fetcher)
        except exc.HTTPException, e:
            return e

    def action_view(self, req, resource_fetcher):
        url = req.GET['url']
        source = int(req.GET.get('source', '0'))
        line = int(req.GET.get('line', '0')) or ''
        selector = req.GET.get('selector', '')
        subresp = resource_fetcher(url)
        if source:
            ct = subresp.content_type
            if ct.startswith('application/xml'):
                lexer = XmlLexer()
            elif ct == 'text/html':
                lexer = HtmlLexer()
            else:
                ## FIXME: what then?
                lexer = HtmlLexer()
            text = pygments_highlight(
                subresp.body, lexer,
                HtmlFormatter(full=True, linenos=True, lineanchors='code'))
        else:
            from deliverance.selector import Selector
            doc = document_fromstring(subresp.body)
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
                els_in_head=els_in_head, doc=doc,
                elements=all_elements, selector=selector, 
                format_tag=format_tag, highlight=highlight)
            message = fromstring(self._message_template.substitute(message=text, url=url))
            if doc.body.text:
                message.tail = doc.body.text
                doc.body.text = ''
            doc.body.insert(0, message)
            text = tostring(doc)
        resp = Response(text)
        return resp

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
        <a href="#{{elements[0][0]}}">jump to element</a>
      {{else}}
        element is in head: {{highlight(elements[0][1])}}
      {{endif}}
    {{else}}
      {{len(elements)}} elements matched the selector <code>{{selector}}</code>:
      <ol>
      {{for anchor, el in elements}}
        {{if anchor}}
          <li><a href="#{{anchor}}"><code>{{format_tag(el)}}</code></a></li>
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

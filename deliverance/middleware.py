from webob import Request
from deliverance.log import SavingLogger
import urllib2

class DeliveranceMiddleware(object):

    def __init__(self, app, rule_getter, log_factory=SavingLogger, log_factory_kw={}):
        self.app = app
        self.rule_getter = rule_getter
        self.log_factory = log_factory
        self.log_factory_kw = log_factory_kw

    def __call__(self, environ, start_response):
        ## FIXME: copy_get?:
        orig_req = Request(environ.copy())
        req = Request(environ)
        log = self.log_factory(req, **self.log_factory_kw)
        resp = req.get_response(self.app)
        ## FIXME: also XHTML?
        if resp.content_type != 'text/html':
            return resp(environ, start_response)
        def get_resource(url):
            assert url is not None
            ## FIXME: should this return a webob.Response object?
            if url.startswith(orig_req.application_url + '/'):
                subreq = orig_req.copy_get()
                subreq.environ['deliverance.subrequest_original_environ'] = orig_req.environ
                new_path_info = url[len(orig_req.application_url):]
                assert new_path_info.startswith('/')
                subreq.path_info = new_path_info
                subresp = subreq.get_response(self.app)
                ## FIXME: error if not HTML?
                ## FIXME: handle redirects?
                ## FIXME: handle non-200?
                return subresp.body
            else:
                ## FIXME: pluggable subrequest handler?
                f = urllib2.urlopen(url)
                body = f.read()
                f.close()
                return body
        rule_set = self.rule_getter(get_resource, self.app, orig_req)
        resp = rule_set.apply_rules(req, resp, get_resource, log)
        return resp(environ, start_response)

class SubrequestRuleGetter(object):

    def __init__(self, url):
        self.url = url
    def __call__(self, get_resource, app, orig_req):
        from deliverance.ruleset import RuleSet
        from lxml.etree import XML, XMLSyntaxError
        import urlparse
        url = urlparse.urljoin(orig_req.url, self.url)
        doc_text = get_resource(url)
        try:
            doc = XML(doc_text, base_url=url)
        except XMLSyntaxError, e:
            raise 'Invalid syntax in %s: %s' % (url, e)
        assert doc.tag == 'ruleset', 'Bad rule tag <%s> in document %s' % (doc.tag, url)
        return RuleSet.parse_xml(doc, url)

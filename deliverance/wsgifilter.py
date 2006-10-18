"""
Deliverance theming as WSGI middleware

Deliverance applies a theme to content.
"""

import re
import urlparse
import urllib
from lxml import etree
#from lxml.etree import HTML as parseHTML 
from htmlserialize import decodeAndParseHTML as parseHTML
from paste.wsgilib import intercept_output
from paste.request import construct_url
from paste.response import header_value, replace_header
from interpreter import Renderer
#from xslt import Renderer
from htmlserialize import tostring
import sys 
import datetime
import threading

DELIVERANCE_BASE_URL = 'deliverance.base-url'

class DeliveranceMiddleware(object):

    def __init__(self, app, theme_uri, rule_uri):
        self.app = app
        self.theme_uri = theme_uri
        self.rule_uri = rule_uri
        self._renderer = None
        self._cache_time = datetime.datetime.now()
        self._timeout = datetime.timedelta(0,10)
        self._lock = threading.Lock()


    def get_renderer(self,environ):
        try:
            self._lock.acquire()
            if not self._renderer or self.cache_expired():
                self._renderer = self.create_renderer(environ)
                self._cache_time = datetime.datetime.now()
            return self._renderer
        finally:
            self._lock.release()

    def create_renderer(self,environ):
        theme = self.theme(environ)
        rule = self.rule(environ)
        full_theme_uri = urlparse.urljoin(
            construct_url(environ, with_path_info=False),
            self.theme_uri)

        def reference_resolver(href, parse, encoding=None):
            text = self.get_resource(environ,href)
            if parse == "xml":
                return etree.XML(text)
            elif encoding:
                return text.decode(encoding)

        return Renderer(
            theme=parseHTML(theme),
            theme_uri=full_theme_uri,
            rule=etree.XML(rule), 
            rule_uri=self.rule_uri,
            reference_resolver=reference_resolver)

        
    def cache_expired(self):
        return self._cache_time + self._timeout < datetime.datetime.now()

    def rule(self, environ):
        return self.get_resource(environ,self.rule_uri)

    def theme(self, environ):
        return self.get_resource(environ,self.theme_uri)

    def __call__(self, environ, start_response):
        qs = environ.get('QUERY_STRING', '')
        environ[DELIVERANCE_BASE_URL] = construct_url(environ, with_path_info=False, with_query_string=False)
        notheme = 'notheme' in qs
        if notheme:
            return self.app(environ, start_response)

        status, headers, body = intercept_output(
            environ, self.app,
            self.should_intercept,
            start_response)


        if status is None:
            # should_intercept returned False
            return body

        body = self.filter_body(environ, body)
        replace_header(headers, 'content-length', str(len(body)))
        replace_header(headers, 'content-type', 'text/html; charset=utf-8')
        start_response(status, headers)
        return [body]

    def should_intercept(self, status, headers):
        type = header_value(headers, 'content-type')
        if type is None:
            return False
        return type.startswith('text/html') or type.startswith('application/xhtml+xml')

    def filter_body(self, environ, body):
        content = self.get_renderer(environ).render(parseHTML(body))
        return tostring(content)

    def get_resource(self, environ, uri):
        internalBaseURL = environ.get(DELIVERANCE_BASE_URL,None)
        uri = urlparse.urljoin(internalBaseURL, uri)
        
        if  internalBaseURL and uri.startswith(internalBaseURL):
            return self.get_internal_resource(environ, uri[len(internalBaseURL):])
        else:
            return self.get_external_resource(uri)

    def relative_uri(self, uri):
        if re.search(r'^[a-zA-Z]+:', uri):
            return False
        else:
            return True

    def get_external_resource(self, uri):
        f = urllib.urlopen(uri)
        content = f.read()
        f.close()
        return content

    def get_internal_resource(self, environ, uri):
        environ = environ.copy()
        if not uri.startswith('/'):
            uri = '/' + uri
        environ['PATH_INFO'] = uri
        environ['SCRIPT_NAME'] = environ[DELIVERANCE_BASE_URL]
        if environ['QUERY_STRING']:
            environ['QUERY_STRING'] += '&notheme'
        else:
            environ['QUERY_STRING'] = 'notheme'

        path_info = environ['PATH_INFO']
        status, headers, body = intercept_output(environ, self.app)
        if not status.startswith('200'):
            loc = header_value(headers, 'location')
            if loc:
                loc = ' location=%r' % loc
            else:
                loc = ''
            raise Exception(
                "Request for internal resource at %s (%r) failed with status code %r%s"
                % (construct_url(environ), path_info, status,
                   loc))
        return body

def make_filter(app, global_conf,
                theme_uri=None, rule_uri=None):
    assert theme_uri is not None, (
        "You must give a theme_uri")
    assert rule_uri is not None, (
        "You must give a rule_uri")
    return DeliveranceMiddleware(
        app, theme_uri, rule_uri)


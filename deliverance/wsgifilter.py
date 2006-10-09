"""
Deliverance theming as WSGI middleware

Deliverance applies a theme to content.
"""

import re
import urlparse
import urllib
from lxml import etree
from paste.wsgilib import intercept_output
from paste.request import construct_url
from paste.response import header_value, replace_header
#from interpreter import Renderer
from xslt import Renderer
from htmlserialize import tostring
import sys 
import datetime
import threading

DELIVERANCE_BASE_URL = 'deliverance-base-url'

class DeliveranceMiddleware(object):

    def __init__(self, app, theme_uri, rule_uri):
        self.app = app
        self.theme_uri = theme_uri
        self.rule_uri = rule_uri
        self._theme = None
        self._rule = None
        self._renderer = None
        self._cache_time = datetime.datetime.now()
        self._timeout = datetime.timedelta(0,10)
        self._lock = threading.Lock()

    def cache_expired(self):
        return self._cache_time + self._timeout < datetime.datetime.now()

    def rule(self, environ):
        if self._rule is None or self.cache_expired():
            self._cache_time = datetime.datetime.now()
            self._renderer = None
            self._rule = self.get_resource(environ, self.rule_uri)
        return self._rule

    def theme(self, environ):
        if self._theme is None or self.cache_expired():
            self._cache_time = datetime.datetime.now()
            self._renderer = None
            self._theme = self.get_resource(environ, self.theme_uri)
        return self._theme
        
    def __call__(self, environ, start_response):
        qs = environ.get('QUERY_STRING', '')
        environ[DELIVERANCE_BASE_URL] = construct_url(environ, with_path_info=False)
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
        return type.startswith('text/html') or type.startswith('application/xhtml+xml')

    def filter_body(self, environ, body):
        try:
            self._lock.acquire()
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

            if not self._renderer:
                self._renderer = Renderer(etree.HTML(theme), full_theme_uri, etree.XML(rule), 
                                          reference_resolver=reference_resolver)

            content = self._renderer.render(etree.HTML(body))
            return tostring(content)
        finally:
                self._lock.release()




    def get_resource(self, environ, uri):
        internalBaseURL = environ.get(DELIVERANCE_BASE_URL,None)
        
        if self.relative_uri(uri):
            return self.get_internal_resource(environ, uri)
        elif internalBaseURL and uri.startswith(internalBaseURL):
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
        status, headers, body = intercept_output(environ, self.app)
        return body

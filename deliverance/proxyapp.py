"""
WSGI proxy application that applies a deliverance theme while
passing the request to another HTTP server
"""

import os
import re
import urlparse
from paste.proxy import TransparentProxy
from paste.urlmap import URLMap
from paste.urlparser import StaticURLParser
from paste.exceptions import errormiddleware
from deliverance.wsgimiddleware import DeliveranceMiddleware
from deliverance.relocateresponse import RelocateMiddleware
from deliverance.utils import get_serializer
from deliverance.utils import set_serializer

class ProxyDeliveranceApp(object):

    def __init__(self, theme_uri, rule_uri, proxy,
                 transparent=False, debug_headers=False,
                 relocate_content=False, renderer='py',
                 serializer=None):
        self.theme_uri = theme_uri,
        self.rule_uri = rule_uri,
        if not re.match(r'https?://', proxy, re.I):
            proxy = 'http://' + proxy
        scheme, netloc, path, query, fragment = urlparse.urlsplit(proxy)
        if fragment:
            raise ValueError(
                "No fragment is allowed in the proxy destination (#%s in the url %r)"
                % (fragment, proxy))
        if query:
            raise ValueError(
                "No query string is allowed in the proxy destination (?%s in the url %r)"
                % (query, proxy))
        if path == '/':
            path = ''
        self.proxy_path = path
        self.proxy = netloc
        if scheme not in ('http', 'https'):
            raise ValueError(
                "Proxying to the scheme %r location is not supported" % scheme)
        self.transparent = transparent
        if self.proxy_path and self.transparent:
            raise ValueError(
                "The transparent option is not compatible with proxy destinations that include"
                " a path (path=%r)" % self.proxy_path)
        self.debug_headers = debug_headers
        self.subapp = self.make_app()
        self.deliverance_app = DeliveranceMiddleware(
            self.subapp, theme_uri, rule_uri, renderer, serializer=serializer)
        self.relocate_content = relocate_content

    def make_app(self):
        if self.transparent:
            force_host = self.proxy
        else:
            force_host = None
        app = TransparentProxy(force_host=force_host)
        if self.debug_headers:
            app = DebugHeaders(app)
        return app

    def __call__(self, environ, start_response):
        if get_serializer(environ, None) is None:
            set_serializer(environ, self.deliverance_app.serializer)
        if self.relocate_content:
            proxy_dest = 'http://%s%s' % (self.proxy, self.proxy_path)
            reloc_app = RelocateMiddleware(self.run_subapp, old_href=proxy_dest)
            return reloc_app(environ, start_response)
        else:
            return self.run_subapp(environ, start_response)

    def run_subapp(self, environ, start_response):
        if not self.transparent:
            # @@: Set forwarded header
            environ['HTTP_HOST'] = self.proxy
            if ':' in self.proxy:
                server, port = self.proxy.split(':', 1)
            else:
                server, port = self.proxy, '80'
            environ['SERVER_NAME'] = server
            environ['SERVER_PORT'] = port
            environ['PATH_INFO'] = self.proxy_path + environ['PATH_INFO']
        return self.deliverance_app(
            environ, start_response)
    

class ProxyMountedDeliveranceApp(ProxyDeliveranceApp):

    def __init__(self, *args, **kw):
        try:
            mount_points = kw.pop('mount_points')
        except KeyError:
            mount_points = {}
        self.mount_points = mount_points
        ProxyDeliveranceApp.__init__(self, *args, **kw)

    def make_app(self):
        normal_app = ProxyDeliveranceApp.make_app(self)
        from paste.urlmap import URLMap
        urlmap = URLMap()
        for name, value in self.mount_points.items():
            urlmap[name] = value
        urlmap['/'] = normal_app
        return urlmap

class DebugHeaders(object):

    translate_keys = {'CONTENT_LENGTH': 'HTTP_CONTENT_LENGTH',
                      'CONTENT_TYPE': 'HTTP_CONTENT_TYPE'}

    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        from paste.request import construct_url
        print 'Incoming headers: (%s %s)' % (
            environ['REQUEST_METHOD'], construct_url(environ))
        for name, value in sorted(environ.items()):
            name = self.translate_keys.get(name, name)
            if not name.startswith('HTTP_'):
                continue
            name = name[5:].replace('_', '-').title()
            print '  %s: %s' % (name, value)
        def repl_start_response(status, headers, exc_info=None):
            print 'Outgoing headers: (%s)' % status
            for name, value in headers:
                print '  %s: %s' % (name.title(), value)
            start_response(status, headers, exc_info)
        return self.app(environ, repl_start_response)


def make_proxy(global_conf,
               wrap_href, theme_uri, rule_uri,
               renderer='py', transparent=False, debug_headers=False,
               relocate_content=False,
               merge_cache_control=False,
               serializer=None,
               **kw):
    from paste.deploy.converters import asbool
    mount_points = {}
    for name, value in kw.items():
        if name.startswith('mount '):
            path = name[len('mount '):].strip()
            if not path:
                raise ValueError('Bad path: %r (in %r)' % (path, name))
            mount_points[path] = StaticURLParser(os.path.abspath(value))
        else:
            raise ValueError(
                "Unexpected configuration key: %r" % name)
    if not wrap_href.startswith('http:') or wrap_href.startswith('https:'):
        wrap_href = 'http://' + wrap_href.lstrip('/')
    parts = urlparse.urlsplit(wrap_href)
    scheme, netloc, path, query, fragment = parts
    scheme = scheme.lower()
    app = ProxyMountedDeliveranceApp(
        theme_uri=theme_uri,
        rule_uri=rule_uri,
        proxy=netloc,
        transparent=asbool(transparent),
        debug_headers=asbool(debug_headers),
        relocate_content=asbool(relocate_content),
        renderer=renderer,
        mount_points=mount_points,
        serializer=serializer)
    app = errormiddleware.make_error_middleware(app, global_conf)
    return app

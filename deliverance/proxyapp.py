"""
WSGI proxy application that applies a deliverance theme while
passing the request to another HTTP server
"""

from paste.proxy import TransparentProxy
from deliverance.wsgimiddleware import DeliveranceMiddleware
from deliverance.relocateresponse import RelocateMiddleware

class ProxyDeliveranceApp(object):

    def __init__(self, theme_uri, rule_uri, proxy,
                 transparent=False, debug_headers=False,
                 relocate_content=False, renderer='py'):
        self.theme_uri = theme_uri,
        self.rule_uri = rule_uri,
        self.proxy = proxy
        self.transparent = transparent
        self.debug_headers = debug_headers
        self.subapp = self.make_app()
        self.deliverance_app = DeliveranceMiddleware(
            self.subapp, theme_uri, rule_uri, renderer)
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
        if self.relocate_content:
            reloc_app = RelocateMiddleware(self.run_subapp, old_href='http://'+self.proxy)
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
        return self.deliverance_app(
            environ, start_response)
    

class DebugHeaders(object):

    translate_keys = {'CONTENT_LENGTH': 'HTTP_CONTENT_LENGTH',
                      'CONTENT_TYPE': 'HTTP_CONTENT_TYPE}

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

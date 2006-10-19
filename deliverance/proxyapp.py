"""
WSGI proxy application that applies a deliverance theme while
passing the request to another HTTP server
"""

from paste.proxy import TransparentProxy
from deliverance import wsgifilter

class ProxyDeliveranceApp(object):

    def __init__(self, theme_uri, rule_uri, proxy,
                 transparent=False):
        self.theme_uri = theme_uri,
        self.rule_uri = rule_uri,
        self.proxy = proxy
        self.transparent = transparent
        self.subapp = self.make_app()
        self.deliverance_app = wsgifilter.DeliveranceMiddleware(
            self.subapp, theme_uri, rule_uri)

    def make_app(self):
        if self.transparent:
            force_host = self.proxy
        else:
            force_host = None
        return TransparentProxy(force_host=force_host)

    def __call__(self, environ, start_response):
        if not self.transparent:
            # @@: Set forwarded header
            environ['HTTP_HOST'] = self.proxy
        return self.deliverance_app(
            environ, start_response)
    

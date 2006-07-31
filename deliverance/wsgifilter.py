"""
Deliverance theming as WSGI middleware

Deliverance applies a theme to content.
"""

import time
from cStringIO import StringIO

from paste.wsgilib import intercept_output
from paste.response import header_value, replace_header
from deliverance.main import AppMap
appmap = AppMap() # Theme is generated once at module import time

class DeliveranceMiddleware(object):

    def __init__(self, app, appmap):
        self.app = app
        self.appmap = appmap

    def __call__(self, environ, start_response):
        qs = environ.get('QUERY_STRING', '')
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
        body = self.filter_body(body)
        replace_header(headers, 'content-length', len(body))
        start_response(status, headers)
        return [body]

    def should_intercept(self, status, headers):
        type = header_value(headers, 'content-type')
        return type.startswith('text/html')

    def filter_body(self, body):
        return appmap.publish(body)

def handler(req):
    """Basic filter applying to all mime types it is registered for"""

    # Get the path, strip off leading slash, and convert to a 
    # dotted notation for xml:id compatibility
    path_info = req.path_info[1:]
    dotted_path = path_info.replace("/", ".")

    response = appmap.publish(dotted_path)
    req.content_type = "text/html"
    req.write(response)

    return apache.OK

"""
Deliverance theming as WSGI middleware
"""

import re
import urlparse
import urllib
from lxml import etree
from htmlserialize import decodeAndParseHTML as parseHTML
from paste.wsgilib import intercept_output
from paste.request import construct_url
from paste.response import header_value, replace_header
from htmlserialize import tostring
from deliverance.utils import DeliveranceError
from deliverance.utils import DELIVERANCE_ERROR_PAGE
import sys 
import datetime
import threading
import traceback
from StringIO import StringIO

DELIVERANCE_BASE_URL = 'deliverance.base-url'


class DeliveranceMiddleware(object):
    """
    a DeliveranceMiddleware object exposes a single deliverance 
    tranformation as a WSGI middleware component. 
    """

    def __init__(self, app, theme_uri, rule_uri, renderer='py'):
        """
        initializer
        
        app: wsgi application which this middleware wraps. 
        theme_uri: uri referring the the theme document 
        rule_uri: uri referring to the deliverance rules document 
        renderer: selects deliverance render class to utilize when 
          performing transformations, may be 'py' or 'xslt' or a
          Renderer class
        """
        self.app = app
        self.theme_uri = theme_uri
        self.rule_uri = rule_uri
        self._renderer = None
        self._cache_time = datetime.datetime.now()
        self._timeout = datetime.timedelta(0,10)
        self._lock = threading.Lock()

        if renderer == 'py':
            import interpreter
            self._rendererType = interpreter.Renderer
        elif renderer == 'xslt':
            import xslt
            self._rendererType = xslt.Renderer
        elif renderer is None or isinstance(renderer, basestring):
            raise ValueError("Unknown Renderer: %s - Expecting 'py' or 'xslt'" % renderer)
        else:
            self._rendererType = renderer

    def get_renderer(self,environ):
        """
        retrieve the deliverance Renderer representing the transformation this 
        middlware represents. Renderer may change according to caching rules. 
        """
        try:
            self._lock.acquire()
            if not self._renderer or self.cache_expired():
                self._renderer = self.create_renderer(environ)
                self._cache_time = datetime.datetime.now()
            return self._renderer
        finally:
            self._lock.release()

    def create_renderer(self,environ):
        """
        construct a new deliverance Renderer from the 
        information passed to the initializer.  A new copy 
        of the theme and rules is retrieved. 
        """
        theme = self.theme(environ)
        rule = self.rule(environ)
        full_theme_uri = urlparse.urljoin(
            construct_url(environ, with_path_info=False),
            self.theme_uri)

        def reference_resolver(href, parse, encoding=None):
            text = self.get_resource(environ,href)
            if parse == "xml":
                return etree.XML(text)
            if parse == "html":
                return etree.HTML(text)
            else:
                if encoding:
                    return text.decode(encoding)
                else:
                    return text

        try:
            parsedTheme = parseHTML(theme)
        except Exception, message:
            newmessage = "Unable to parse theme page (" + self.theme_uri + ")"
            if message:
                newmessage += ":" + str(message)
            raise DeliveranceError(newmessage)

        try:
            parsedRule = etree.XML(rule)
        except Exception, message:
            newmessage = "Unable to parse rules (" + self.rule_uri + ")"
            if message:
                newmessage += ":" + str(message)
            raise DeliveranceError(newmessage)

        return self._rendererType(
            theme=parsedTheme,
            theme_uri=full_theme_uri,
            rule=parsedRule, 
            rule_uri=self.rule_uri,
            reference_resolver=reference_resolver)

        
    def cache_expired(self):
        """
        returns true if the stored Renderer should be refreshed 
        """
        return self._cache_time + self._timeout < datetime.datetime.now()

    def rule(self, environ):
        """
        retrieves the data referred to by the rule_uri passed to the 
        initializer. 
        """
        try:
            return self.get_resource(environ,self.rule_uri)
        except Exception, message:
            newmessage = "Unable to retrieve rules from " + self.rule_uri 
            if message:
                newmessage += ": " + str(message)

            raise DeliveranceError(newmessage)

    def theme(self, environ):
        """
        retrieves the data referred to by the theme_uri passed to the 
        initializer. 
        """
        try:
            return self.get_resource(environ,self.theme_uri)
        except Exception, message:
            newmessage = "Unable to retrieve theme page from " + self.theme_uri 
            if message:
                newmessage += ": " + str(message)
            raise DeliveranceError(newmessage)


    def __call__(self, environ, start_response):
        """
        WSGI entrypoint, responds to the request in 
        environ. responses from the wrapped WSGI 
        application of type text/html are themed 
        using the transformation specified in the 
        initializer. 
        """
        try:
            qs = environ.get('QUERY_STRING', '')
            environ[DELIVERANCE_BASE_URL] = construct_url(environ, with_path_info=False, with_query_string=False)
            notheme = 'notheme' in qs
            if notheme:
                return self.app(environ, start_response)
            if 'HTTP_ACCEPT_ENCODING' in environ:
                del environ['HTTP_ACCEPT_ENCODING']

            status, headers, body = intercept_output(
                environ, self.app,
                self.should_intercept,
                start_response)

            # ignore non-html responses 
            if status is None:
                return body

            # don't theme html snippets 
            if self.hasHTMLTag(body):
                body = self.filter_body(environ, body)

            replace_header(headers, 'content-length', str(len(body)))
            replace_header(headers, 'content-type', 'text/html; charset=utf-8')
            start_response(status, headers)
            return [body]
        
        except DeliveranceError, message:            
            stack = StringIO()
            traceback.print_exception(sys.exc_info()[0],
                                      sys.exc_info()[1],
                                      sys.exc_info()[2],
                                      file=stack)
            status = "500 Internal Server Error"
            headers = [('Content-type','text/html')]
            start_response(status,headers)
            errpage = DELIVERANCE_ERROR_PAGE % (message,stack.getvalue())
            return [ errpage ]

    def should_intercept(self, status, headers):
        """
        returns true if the status and headers given 
        specify a response from the wrapped middleware 
        which deliverance may need to theme. 
        """
        type = header_value(headers, 'content-type')
        if type is None:
            return False
        return type.startswith('text/html') or type.startswith('application/xhtml+xml')

    def filter_body(self, environ, body):
        """
        returns the result of the deliverance transformation on the string 'body' 
        in the context of environ. The result is a string containing HTML. 
        """
        content = self.get_renderer(environ).render(parseHTML(body))
        return tostring(content)

    def get_resource(self, environ, uri):
        """
        retrieve the data referred to by the uri given. 
        """
        internalBaseURL = environ.get(DELIVERANCE_BASE_URL,None)
        uri = urlparse.urljoin(internalBaseURL, uri)
        
        if  internalBaseURL and uri.startswith(internalBaseURL):
            return self.get_internal_resource(environ, uri[len(internalBaseURL):])
        else:
            return self.get_external_resource(uri)

    def relative_uri(self, uri):
        """
        returns true if uri is relative, false if 
        the uri is absolute. 
        """
        if re.search(r'^[a-zA-Z]+:', uri):
            return False
        else:
            return True

    def get_external_resource(self, uri):
        """
        get the data referred to by the uri given 
        using urllib (not through the wrapped app)
        """
        f = urllib.urlopen(uri)
        content = f.read()
        f.close()
        return content

    def get_internal_resource(self, in_environ, uri):
        """
        get the data referred to by the uri given 
        by using the wrapped WSGI application 
        """

        
        if 'paste.recursive.include' in in_environ:
            environ = in_environ['paste.recursive.include'].original_environ.copy()
        else:
            environ = in_environ.copy()
            
        if not uri.startswith('/'):
            uri = '/' + uri
        environ['PATH_INFO'] = uri
        environ['SCRIPT_NAME'] = in_environ[DELIVERANCE_BASE_URL]
        environ['REQUEST_METHOD'] = 'GET'
        environ['CONTENT_LENGTH'] = '0'
        environ['wsgi.input'] = StringIO('')
        environ['CONTENT_TYPE'] = ''
        if environ['QUERY_STRING']:
            environ['QUERY_STRING'] += '&notheme'
        else:
            environ['QUERY_STRING'] = 'notheme'

        if 'HTTP_ACCEPT_ENCODING' in environ:
	    environ['HTTP_ACCEPT_ENCODING'] = '' 

        if 'paste.recursive.include' in in_environ:
            # Try to do the redirect this way...
            includer = in_environ['paste.recursive.include']
            res = includer(uri,environ)
            return res.body


        path_info = environ['PATH_INFO']
        status, headers, body = intercept_output(environ, self.app)
        if not status.startswith('200'):
            loc = header_value(headers, 'location')
            if loc:
                loc = ' location=%r' % loc
            else:
                loc = ''
            raise DeliveranceError(
                "Request for internal resource at %s (%r) failed with status code %r%s"
                % (construct_url(environ), path_info, status,
                   loc))
        return body

    HTML_DOC_PAT = re.compile(r"^.*<\s*html(\s*|>).*$",re.I|re.M)
    def hasHTMLTag(self, body):
        """
        a quick and dirty check to see if some text contains 
        anything that looks like an html tag. This could 
        certainly be improved if needed or there are 
        ambiguous tags 
        """
        return self.HTML_DOC_PAT.search(body) is not None

def make_filter(app, global_conf,
                theme_uri=None, rule_uri=None):
    assert theme_uri is not None, (
        "You must give a theme_uri")
    assert rule_uri is not None, (
        "You must give a rule_uri")
    return DeliveranceMiddleware(
        app, theme_uri, rule_uri)


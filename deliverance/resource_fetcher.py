import urllib
import deliverance.wsgimiddleware 
from StringIO import StringIO
from paste.wsgilib import intercept_output
from paste.proxy import TransparentProxy 
from paste.request import construct_url
from paste.response import header_value
from paste.fileapp import FileApp
import urlparse
from deliverance.utils import DeliveranceError


class InternalResourceFetcher(object): 
    def __init__(self, in_environ, uri, app, headers_only=False): 
        self.uri = uri 
        self.app = app 

        if 'paste.recursive.include' in in_environ:
            self.environ = in_environ['paste.recursive.include'].original_environ.copy()
            self.environ['paste.recursive.include'] = in_environ['paste.recursive.include']
        else:
            self.environ = in_environ.copy()
            
        if not self.uri.startswith('/'):
            self.uri = '/' + self.uri

        uri_parts = urlparse.urlparse(uri)

        self.environ['PATH_INFO'] = urllib.unquote(uri_parts[2])
        if len(uri_parts[4]) > 0: 
            self.environ['QUERY_STRING'] = uri_parts[4] + '&notheme'
        else: 
            self.environ['QUERY_STRING'] = 'notheme'

        base_url = in_environ['deliverance.base-url']
        if base_url is not None:
            self.environ['SCRIPT_NAME'] = urllib.unquote(urlparse.urlparse(base_url)[2])
        else: 
            self.environ['SCRIPT_NAME'] = ''

        if headers_only: 
            self.environ['REQUEST_METHOD'] = 'HEAD'
        else: 
            self.environ['REQUEST_METHOD'] = 'GET'

        self.environ['CONTENT_LENGTH'] = '0'
        self.environ['wsgi.input'] = StringIO('')
        self.environ['CONTENT_TYPE'] = ''


        if 'HTTP_ACCEPT_ENCODING' in self.environ:
	    self.environ['HTTP_ACCEPT_ENCODING'] = '' 

    def wsgi_get(self): 
        if 'paste.recursive.include' in self.environ: 
            # Try to do the redirect this way...
            includer = self.environ['paste.recursive.include']
            return intercept_output(self.environ, includer.application)
        else: 
            status, headers, body = intercept_output(self.environ, self.app)
            return (status, headers, body)


    def get(self): 
        path_info = self.environ['PATH_INFO']
        status, headers, body = self.wsgi_get()

        if not status.startswith('200'):
            loc = header_value(headers, 'location')
            if loc:
                loc = ' location=%r' % loc
            else:
                loc = ''
            raise DeliveranceError(
                "Request for internal resource at %s (%r) failed with status code %r%s"
                % (construct_url(self.environ), path_info, status,
                   loc))
        return body

class FileResourceFetcher(object):
    def __init__(self, environ, uri, headers_only=False):
        self.environ = environ.copy()
        self.uri = uri

        uri_parts = urlparse.urlparse(self.uri)
        self.environ['PATH_INFO'] = uri_parts[2]
        self.environ['SCRIPT_NAME'] = '' 
        self.environ['wsgi.scheme'] = 'file'
        if len(uri_parts[4]) > 0: 
            self.environ['QUERY_STRING'] = uri_parts[4] + '&notheme'
        else: 
            self.environ['QUERY_STRING'] = 'notheme'

        if headers_only:
            self.environ['REQUEST_METHOD'] = 'HEAD'
        else:
            self.environ['REQUEST_METHOD'] = 'GET'

        self.environ['CONTENT_LENGTH'] = '0'
        self.environ['wsgi.input'] = StringIO('')
        self.environ['CONTENT_TYPE'] = '' 

        if 'HTTP_ACCEPT_ENCODING' in self.environ:
            del self.environ['HTTP_ACCEPT_ENCODING']

    def wsgi_get(self):
        path = urlparse.urlparse(self.uri)[2]
        file_app = FileApp(path)

        return intercept_output(self.environ, file_app)
        

    def get(self):
        path_info = self.environ['PATH_INFO']
        status, headers, body = self.wsgi_get()

        if not status.startswith('200'):
            loc = header_value(headers, 'location')
            if loc:
                loc = ' location=%r' % loc
            else:
                loc = ''
            raise DeliveranceError(
                "Request for file at %s (%r) failed with status code %r%s"
                % (construct_url(self.environ), path_info, status,
                   loc))
        return body

class ExternalResourceFetcher(object): 
    def __init__(self, in_environ, uri, headers_only=False): 
        self.uri = uri 
        
        url_chunks = urlparse.urlsplit(uri)
        loc = urlparse.urlsplit(uri) 
        
        self.environ = in_environ.copy() 
        
        if headers_only: 
            self.environ['REQUEST_METHOD'] = 'HEAD'
        else:
            self.environ['REQUEST_METHOD'] = 'GET'

        self.environ['CONTENT_LENGTH'] = '0'
        self.environ['wsgi.input'] = StringIO('')

        self.environ['wsgi.url_scheme'] = loc[0]
        self.environ['wsgi.version'] = (1, 0)
        self.environ['HTTP_HOST'] = loc[1]
        self.environ['PATH_INFO'] = urllib.unquote(loc[2])
        self.environ['QUERY_STRING'] = loc[3]

        self.environ['SCRIPT_NAME'] = ''

        #if loc[0].find(':') != -1: 
        #    self.environ['SERVER_NAME'],self.environ['SERVER_PORT'] = loc[0].split(':')
        #else: 
        #    self.environ['SERVER_NAME'] = loc[0]
        #    if loc[0] == 'https': 
        #        self.environ['SERVER_PORT'] = '443'
        #    else: 
        #        self.environ['SERVER_PORT'] = '80'

    def wsgi_get(self): 
        proxy_app = TransparentProxy() 
        return intercept_output(self.environ, proxy_app)

    def get(self): 
        status, headers, body = self.wsgi_get()

        if not status.startswith('200'):
            loc = header_value(headers, 'location')
            if loc:
                loc = ' location=%r' % loc
            else:
                loc = ''
            raise DeliveranceError(
                "Request for external resource at %s failed with status code %r%s"
                % (construct_url(self.environ), status,
                   loc))

        return body 

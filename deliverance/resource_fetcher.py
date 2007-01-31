import deliverance.wsgimiddleware 
from StringIO import StringIO
from paste.wsgilib import intercept_output
from paste.proxy import TransparentProxy 
from paste.request import construct_url
from paste.response import header_value
import urlparse
from deliverance.utils import DeliveranceError


class InternalResourceFetcher(object): 
    def __init__(self, in_environ, uri, app, headers_only=False): 
        self.uri = uri 
        self.app = app 

        if 'paste.recursive.include' in in_environ:
            self.environ = in_environ['paste.recursive.include'].original_environ.copy()
        else:
            self.environ = in_environ.copy()
            
        if not self.uri.startswith('/'):
            self.uri = '/' + self.uri

        self.environ['PATH_INFO'] = uri

        base_url = in_environ['deliverance.base-url']
        if base_url is not None:
            self.environ['SCRIPT_NAME'] = urlparse.urlparse(base_url)[2]
        else: 
            self.environ['SCRIPT_NAME'] = ''

        if headers_only: 
            self.environ['REQUEST_METHOD'] = 'HEAD'
        else: 
            self.environ['REQUEST_METHOD'] = 'GET'

        self.environ['CONTENT_LENGTH'] = '0'
        self.environ['wsgi.input'] = StringIO('')
        self.environ['CONTENT_TYPE'] = ''
        self.environ['QUERY_STRING'] = 'notheme'

        if 'HTTP_ACCEPT_ENCODING' in self.environ:
	    self.environ['HTTP_ACCEPT_ENCODING'] = '' 

    def wsgi_get(self): 
        print "Internal Resource get: %s" % self.uri
        if 'paste.recursive.include' in self.environ: 
            print "Doing paste.recursive.include"
            # Try to do the redirect this way...
            includer = self.environ['paste.recursive.include']
            res = includer(self.uri, self.environ)
            return (res.status, res.headers, res.body)
        else: 
            print "Doing intercept"
            return intercept_output(self.environ, self.app)


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


class ExternalResourceFetcher(object): 
    def __init__(self, uri, headers_only=False): 
        self.uri = uri 
        
        url_chunks = urlparse.urlsplit(uri)
        loc = urlparse.urlsplit(uri) 
        
        self.environ = {}
        
        if headers_only: 
            self.environ['REQUEST_METHOD'] = 'HEAD'
        else:
            self.environ['REQUEST_METHOD'] = 'GET'

        self.environ['CONTENT_LENGTH'] = '0'
        self.environ['wsgi.input'] = StringIO('')

        self.environ['wsgi.url_scheme'] = loc[0]
        self.environ['wsgi.version'] = (1, 0)
        self.environ['HTTP_HOST'] = loc[1]
        self.environ['PATH_INFO'] = loc[2]
        self.environ['QUERY_STRING'] = loc[3]

        self.environ['SCRIPT_INFO'] = ''

        #if loc[0].find(':') != -1: 
        #    self.environ['SERVER_NAME'],self.environ['SERVER_PORT'] = loc[0].split(':')
        #else: 
        #    self.environ['SERVER_NAME'] = loc[0]
        #    if loc[0] == 'https': 
        #        self.environ['SERVER_PORT'] = '443'
        #    else: 
        #        self.environ['SERVER_PORT'] = '80'

    def wsgi_get(self): 
        print "External Resource get: %s" % self.uri
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

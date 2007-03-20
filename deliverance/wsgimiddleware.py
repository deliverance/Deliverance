

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
from deliverance.resource_fetcher import InternalResourceFetcher, FileResourceFetcher, ExternalResourceFetcher
from deliverance import cache_utils
import sys 
import datetime
import threading
import traceback
from StringIO import StringIO
from sets import Set

DELIVERANCE_BASE_URL = 'deliverance.base-url'
DELIVERANCE_CACHE = 'deliverance.cache'

IGNORE_EXTENSIONS = ['js','css','gif','jpg','jpeg','pdf','ps','doc','png','ico','mov','mpg','mpeg', 'mp3','m4a', 
                     'txt','rtf', 'swf', 'wav', 'zip', 'wmv', 'ppt', 'gz', 'tgz', 'jar', 'xls', 'bmp', 'tif', 'tga', 
                     'hqx', 'avi']

IGNORE_URL_PATTERN = re.compile("^.*\.(%s)$" % '|'.join(IGNORE_EXTENSIONS))

class DeliveranceMiddleware(object):
    """
    a DeliveranceMiddleware object exposes a single deliverance 
    tranformation as a WSGI middleware component. 
    """

    def __init__(self, app, theme_uri, rule_uri, renderer='py', merge_cache_control=False):
        """
        initializer
        
        app: wsgi application which this middleware wraps. 
        theme_uri: uri referring the the theme document 
        rule_uri: uri referring to the deliverance rules document 
        renderer: selects deliverance render class to utilize when 
          performing transformations, may be 'py' or 'xslt' or a
          Renderer class
        merge_cache_control: if set to True, the cache-control header will 
        be calculated from the cache-control headers of all component pages 
        during rendering. If set to False, the requested content's 
        cache-control headers will be used. (does not affect etag merging)
        """
        self.app = app
        self.theme_uri = theme_uri
        self.rule_uri = rule_uri
        self.merge_cache_control = merge_cache_control

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

    def get_renderer(self, environ):
        return self.create_renderer(environ)

    def create_renderer(self, environ):
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
            text = self.get_resource(environ, href)
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
            message.public_html = 'Cannot parse rules (%s)' % message
            raise

        return self._rendererType(
            theme=parsedTheme,
            theme_uri=full_theme_uri,
            rule=parsedRule, 
            rule_uri=self.rule_uri,
            reference_resolver=reference_resolver)

    def rule(self, environ):
        """
        retrieves the data referred to by the rule_uri passed to the 
        initializer. 
        """
        try:
            return self.get_resource(environ, self.rule_uri)
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
            return self.get_resource(environ, self.theme_uri)
        except Exception, message:
            message.public_html = 'Unable to retrieve theme page from %s: %s' % (
                self.theme_uri, message)
            raise

    def __call__(self, environ, start_response):
        """
        WSGI entrypoint, responds to the request in 
        environ. responses from the wrapped WSGI 
        application of type text/html are themed 
        using the transformation specified in the 
        initializer. 
        """
        qs = environ.get('QUERY_STRING', '')
        environ[DELIVERANCE_BASE_URL] = construct_url(environ, with_path_info=False, with_query_string=False)
        environ[DELIVERANCE_CACHE] = {} 
        notheme = 'notheme' in qs
        if environ.get('HTTP_X_REQUESTED_WITH', '') == 'XMLHttpRequest':
            notheme = True
        if notheme:
            # eliminate the deliverance notheme query argument for the subrequest
            if qs == 'notheme': 
                environ['QUERY_STRING'] = ''
            elif qs.endswith('&notheme'): 
                environ['QUERY_STRING'] = qs[:-len('&notheme')]
            return self.app(environ, start_response)
        
        # unsupported 
        if 'HTTP_ACCEPT_ENCODING' in environ:
            environ['HTTP_ACCEPT_ENCODING'] = '' 
        if 'HTTP_IF_MATCH' in environ: 
            del environ['HTTP_IF_MATCH'] 
        if 'HTTP_IF_UNMODIFIED_SINCE' in environ: 
            del environ['HTTP_IF_UNMODIFIED_SINCE'] 
            
        status, headers, body = self.rebuild_check(environ, start_response)

        # non-html responses, or rebuild is not necessary: bail out 
        if status is None:
            return body

        # perform actual themeing 
        body = self.filter_body(environ, body)

        replace_header(headers, 'content-length', str(len(body)))
        replace_header(headers, 'content-type', 'text/html; charset=utf-8')

        cache_utils.merge_cache_headers(environ, 
                                        environ[DELIVERANCE_CACHE], 
                                        headers, 
                                        self.merge_cache_control)

        start_response(status, headers)
        return [body]
        
    def should_intercept(self, status, headers):
        """
        returns true if the status and headers given 
        specify a response from the wrapped middleware 
        which deliverance may need to theme. 
        """
        type = header_value(headers, 'content-type')
        if type is None:
            return False # yerg, 304s can have no content-type 
        return type.startswith('text/html') or type.startswith('application/xhtml+xml')

    def filter_body(self, environ, body):
        """
        returns the result of the deliverance transformation on the string 'body' 
        in the context of environ. The result is a string containing HTML. 
        """
        content = self.get_renderer(environ).render(parseHTML(body))

        return tostring(content, doctype_pair=("-//W3C//DTD HTML 4.01 Transitional//EN",
                                               "http://www.w3.org/TR/html4/loose.dtd"))


    def rebuild_check(self, environ, start_response): 
        # perform the request for content  

        content_url = construct_url(environ)

        etag_map = {}
        if 'HTTP_IF_NONE_MATCH' in environ: 
            etag_map = cache_utils.parse_merged_etag(environ['HTTP_IF_NONE_MATCH'])
	    tag = etag_map.get(content_url, None)
	    environ['HTTP_IF_NONE_MATCH'] = tag
	    if tag: 
                environ['HTTP_IF_NONE_MATCH'] = tag
            else:
                if 'HTTP_IF_NONE_MATCH' in environ: 
                    del environ['HTTP_IF_NONE_MATCH']


        status, headers, body = intercept_output(environ, self.app,
                                                 self.should_intercept,
                                                 start_response)            


        if status is None: 
            # should_intercept says this isn't HTML, we're done
            return (None, None, body)

        if self.should_ignore_url(content_url): 
            start_response(status, headers)
            return (None, None, [body])

        # cache the response so we can look at its headers later 
        environ[DELIVERANCE_CACHE][content_url] = (status, headers, body)

        # it was modified or an error, give it back for themeing 
        if not status.startswith('304'): 
            # if it's not a full HTML page, skip it 
            if not self.hasHTMLTag(body): 
                start_response(status, headers)
                return (None, None, [body])

            # send it back for rebuild 
            return (status, headers, body)
            
        # got 304 Not Modified for content, check other resources 
        rules = etree.XML(self.rule(environ))
        resources = self.get_resource_uris(rules)        
        if self.any_modified(environ, resources, etag_map): 
            # something changed, 
            # get the content explicitly and give it back 
            if 'HTTP_IF_MODIFIED_SINCE' in environ: 
                del environ['HTTP_IF_MODIFIED_SINCE']
            if 'HTTP_IF_NONE_MATCH' in environ: 
                del environ['HTTP_IF_NONE_MATCH'] 
            environ['CACHE-CONTROL'] = 'no-cache'

            status, headers, body = intercept_output(environ, self.app)

            if not self.hasHTMLTag(body): 
                # XXX yarg, we didn't care about it!
                start_response(status, headers)
                return (None, None, [body])

            environ[DELIVERANCE_CACHE][content_url] = (status, headers, body)
            return (status, headers, body)

        # nothing was modified, give back a 304 
        cache_utils.merge_cache_headers(environ, 
                                        environ[DELIVERANCE_CACHE], 
                                        headers, 
                                        self.merge_cache_control)
        start_response('304 Not Modified', headers)

        return (None,None,[])
        
    def any_modified(self, environ, resources, etag_map): 
        """
        returns a boolean indicating whether any of the uris in the resources 
        list have been modified. if an entry for the uri exists in the map
        etag_map, the value will be used to check the resource using an 
        if-none-match http header. if an if-not-modified check is desired, 
        it should be present in environ. 
        """
        moddate = None

        if 'HTTP_IF_MODIFIED_SINCE' in environ: 
            moddate = environ['HTTP_IF_MODIFIED_SINCE']            
            
        for uri in resources:
            if (self.check_modification(environ, uri, 
                                        moddate, 
                                        etag_map.get(uri,None))): 
                return True

        return False 


    def get_resource(self, environ, uri):
        """
        retrieve the content from the uri given, 
        uses cache if possible. throws exception if 
        response is not 200 
        """
        if uri in environ[DELIVERANCE_CACHE]: 
            response = environ[DELIVERANCE_CACHE][uri]
            if response[0].startswith('200'): 
                return response[2]

        fetcher = self.get_fetcher(environ, uri)
         

        # eliminate validation headers, we want the content 
        if 'HTTP_IF_MODIFIED_SINCE' in fetcher.environ: 
            del fetcher.environ['HTTP_IF_MODIFIED_SINCE']
        if 'HTTP_IF_NONE_MATCH' in fetcher.environ: 
            del fetcher.environ['HTTP_IF_NONE_MATCH'] 
        fetcher.environ['CACHE-CONTROL'] = 'no-cache'
        

        status, headers, body = fetcher.wsgi_get()         
        
        if not status.startswith('200'): 
            path_info = uri 
            loc = header_value(headers, 'location')
            if loc:
                loc = ' location=%r' % loc
            else:
                loc = ''
            raise DeliveranceError(
                "Request for internal resource at %s (%r) failed with status code %r%s"
                % (construct_url(environ), path_info, status,
                   loc))

        environ[DELIVERANCE_CACHE][uri] = (status, headers, body)

        return body
            

    def get_fetcher(self, environ, uri): 
        """
        retrieve an object which is appropriate for fetching the 
        uri specified. 
        """
        internalBaseURL = environ.get(DELIVERANCE_BASE_URL,None)
        uri = urlparse.urljoin(internalBaseURL, uri)        

        if urlparse.urlparse(uri)[0] == 'file':
            return FileResourceFetcher(environ, uri)

        elif  internalBaseURL and uri.startswith(internalBaseURL):
            return InternalResourceFetcher(environ, uri[len(internalBaseURL):],
                                           self.app)
        else:
            return ExternalResourceFetcher(uri)        


    def get_resource_uris(self, rules): 
        """
        retrieves a list of uris pointing to the resources that 
        are components of rendering (excluding content) 
        """
        resources = Set()
        resources.add(self.rule_uri)
        resources.add(self.theme_uri)

        for rule in rules: 
            href = rule.get("href",None)
            if href is not None:
                resources.add(href)

        return list(resources)

            
    def check_modification(self, environ, uri, httpdate_since=None, etag=None): 
        """
        if httpdate_since is set to an httpdate the If-Modified-Since HTTP header 
          is used to check for modification 

        if etag is set to an etag for the resource, the If-None-Match HTTP header 
          is used to check for modification 

        the resulting (status, headers, body) tuple for the request is stored in 
        environ[DELIVERANCE_CACHE][uri]. 

        """

        fetcher = self.get_fetcher(environ, uri)
        
        if httpdate_since: 
            fetcher.environ['HTTP_IF_MODIFIED_SINCE'] = httpdate_since 
        else: 
            if 'HTTP_IF_MODIFIED_SINCE' in fetcher.environ: 
                del fetcher.environ['HTTP_IF_MODIFIED_SINCE']
        

        if etag: 
            fetcher.environ['HTTP_IF_NONE_MATCH'] = etag
        else: 
            if 'HTTP_IF_NONE_MATCH' in fetcher.environ: 
                del fetcher.environ['HTTP_IF_NONE_MATCH']


        status, headers, body = fetcher.wsgi_get()
        environ[DELIVERANCE_CACHE][uri] = (status, headers, body)

        if status.startswith('304'): # Not Modified             
            return False 

        return True



    HTML_DOC_PAT = re.compile(r"^.*<\s*html(\s*|>).*$",re.I|re.M)
    def hasHTMLTag(self, body):
        """
        a quick and dirty check to see if some text contains 
        anything that looks like an html tag. This could 
        certainly be improved if needed or there are 
        ambiguous tags 
        """
        return self.HTML_DOC_PAT.search(body) is not None


    def should_ignore_url(self, url): 
        # blacklisting can happen here as well 
        return re.match(IGNORE_URL_PATTERN, url) is not None

def make_filter(app, global_conf,
                theme_uri=None, rule_uri=None):
    assert theme_uri is not None, (
        "You must give a theme_uri")
    assert rule_uri is not None, (
        "You must give a rule_uri")
    return DeliveranceMiddleware(
        app, theme_uri, rule_uri)




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
from wsgifilter.cache_utils import parse_merged_etag #this version must be a bit difference than the deli version
from wsgifilter.resource_fetcher import *
import sys 
import datetime
import threading
import traceback
from StringIO import StringIO
from sets import Set
from transcluder.tasklist import PageManager, TaskList
from transcluder.deptracker import DependencyTracker
from transcluder.cookie_wrapper import * 
from transcluder.middleware import is_conditional_get

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

    def __init__(self, app, theme_uri, rule_uri, renderer='py', merge_cache_control=False, deptracker = None, tasklist = None):
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

        if tasklist:
            self.tasklist = tasklist
        else:
            self.tasklist = TaskList()

        if deptracker:
            self.deptracker = deptracker
        else:
            self.deptracker = DependencyTracker()

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

    def get_rules(self, fetch):
        try:
            status, headers, body, parsed = fetch(self.rule_uri)
            if not status.startswith('200'):
                raise DeliveranceError("Unable to retrieve rules from %s (status = %s)" % (self.rule_uri, status))
            
        except Exception, message:
            newmessage = "Unable to retrieve rules from %s " % self.rule_uri 
            if message:
                newmessage += ": " + str(message)

            raise DeliveranceError(newmessage)

        try:
            parsed_rules = etree.XML(body)
        except Exception, message:
            message.public_html = 'Cannot parse rules (%s) [%s]' % (message, rule)
            raise

        return parsed_rules
    
    def get_theme(self, fetch):
        try:
            status, headers, body, parsed = fetch(self.theme_uri)
            if not status.startswith('200'):
                raise DeliveranceError("Unable to retrieve theme from %s (status = %s)" % (self.rule_uri, status))
            return parsed
        except Exception, message:
            message.public_html = 'Unable to retrieve theme page from %s: %s' % (
                self.theme_uri, message)
            raise

    def create_renderer(self, environ, page_manager):
        """
        construct a new deliverance Renderer from the 
        information passed to the initializer.  A new copy 
        of the theme and rules is retrieved. 
        """

        def reference_resolver(href, parse, encoding=None):
            status, headers, body, parsed = page_manager.fetch(href)

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

            if parse == "html":
                return parsed 
            if parse == "xml":
                return etree.XML(text)
            else:
                if encoding:
                    return text.decode(encoding)
                else:
                    return text
                
        full_theme_uri = urlparse.urljoin(
            construct_url(environ, with_path_info = False),
            self.theme_uri)


        parsedTheme = self.get_theme(page_manager.fetch)
        parsedRule = self.get_rules(page_manager.fetch)
        
        try:
            parsedRule =  etree.XML(page_manager.fetch(self.rule_uri)[2])
        except Exception, message:
            newmessage = "Unable to retrieve rules from " + self.rule_uri 
            if message:
                newmessage += ": " + str(message)
            raise DeliveranceError(newmessage)
        
        return self._rendererType(
            theme=parsedTheme,
            theme_uri=full_theme_uri,
            rule=parsedRule, 
            rule_uri=self.rule_uri,
            reference_resolver=reference_resolver)

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
    

        environ['transcluder.outcookies'] = {}
        if environ.has_key('HTTP_COOKIE'):
            environ['transcluder.incookies'] = expire_cookies(unwrap_cookies(environ['HTTP_COOKIE']))
        else:
            environ['transcluder.incookies'] = {}


        if environ.has_key('HTTP_IF_NONE_MATCH'): 
            environ['transcluder.etags'] = parse_merged_etag(environ['HTTP_IF_NONE_MATCH'])
        else: 
            environ['transcluder.etags'] = {}


        pm = PageManager(construct_url(environ), environ, self.deptracker,
                         lambda document, document_url: self.find_deps(environ, document, document_url),
                         self.tasklist, self.etree_subrequest)
        self.pm = pm

        if is_conditional_get(environ) and not pm.is_modified():
            headers = [] 
            pm.merge_headers_into(headers)
            start_response('304 Not Modified', headers)
            return []

        status, headers, body, parsed = pm.fetch(construct_url(environ))

        #ajax
        if not self.hasHTMLTag(body): 
            start_response(status, headers)
            return [body]

        pm.begin_speculative_gets()

        # perform actual themeing

        themed_doc = self.create_renderer(environ, pm).render(parsed)
        body = tostring(themed_doc, doctype_pair=("-//W3C//DTD HTML 4.01 Transitional//EN",
                                                  "http://www.w3.org/TR/html4/loose.dtd"))

        replace_header(headers, 'content-length', str(len(body)))
        replace_header(headers, 'content-type', 'text/html; charset=utf-8')

        pm.merge_headers_into(headers)

        start_response(status, headers)
        return [body]

    def is_html(self, status, headers):
        type = header_value(headers, 'content-type')
        return type and (type.startswith('text/html') or type.startswith('application/xhtml+xml'))

    def etree_subrequest(self, url, environ):

        url = urllib.unquote(url)

        url_parts = urlparse.urlparse(url)
        env = environ.copy()

        env['PATH_INFO'] = url_parts[2]
        if len(url_parts[4]):
            env['QUERY_STRING'] = url_parts[4]

        request_url = construct_url(environ, with_path_info=False, with_query_string=False)
        request_url_parts = urlparse.urlparse(request_url)

        #import pdb;pdb.set_trace()

        if request_url_parts[0:2] == url_parts[0:2]:
            status, headers, body = get_internal_resource(url, env, self.app)
        elif url_parts[0:2] == ('', ''):
            status, headers, body = get_internal_resource(urlparse.urlunparse(request_url_parts[0:2] + url_parts[2:]), env, self.app)
        else:
            status, headers, body = get_external_resource(url, env)
        


        if status.startswith('200') and self.is_html(status, headers):
            parsed = etree.HTML(body)
        else:
            parsed = None
        return status, headers, body, parsed

    #fixme: is this the same as get_resource_uris?
    def find_deps(self, environ, document, document_url):        
        if document_url == construct_url(environ):
            return [self.theme_uri, self.rule_uri]
        elif document_url == self.theme_uri:
            return []
        elif document_url == self.rule_uri:
            return self.get_resource_uris(document)
            #FIXME: check rules for xincludes.
        return []

        
        
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


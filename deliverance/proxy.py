"""
Implements everything related to proxying
"""

import urllib
import posixpath
import urlparse
import re
import socket
import os
import string
import tempfile
from deliverance.util.proxyrequest import Request, Response
from webob import exc
from wsgiproxy.exactproxy import proxy_exact_request
from tempita import html_quote
from paste.fileapp import FileApp
from lxml.etree import tostring as xml_tostring, Comment, parse
from lxml.html import document_fromstring, tostring
from deliverance.exceptions import DeliveranceSyntaxError, AbortProxy
from deliverance.pagematch import AbstractMatch
from deliverance.util.converters import asbool
from deliverance.middleware import DeliveranceMiddleware
from deliverance.ruleset import RuleSet
from deliverance.log import SavingLogger
from deliverance.util.uritemplate import uri_template_substitute
from deliverance.util.nesteddict import NestedDict
from deliverance.security import execute_pyref, edit_local_files
from deliverance.pyref import PyReference
from deliverance.util.filetourl import filename_to_url, url_to_filename
from deliverance.util.urlnormalize import url_normalize
from deliverance.editor.editorapp import Editor

class ProxySet(object):
    """
    A container for all the ``<proxy>`` (`Proxy`) objects in a
    ruleset.
    """

    def __init__(self, proxies, ruleset, source_location=None):
        self.proxies = proxies
        self.ruleset = ruleset
        self.source_location = source_location
        self.deliverator = DeliveranceMiddleware(self.proxy_app, self.rule_getter)

    @classmethod
    def parse_xml(cls, el, source_location):
        """Parse an instance from an XML/etree element"""
        proxies = []
        for child in el:
            if child.tag == 'proxy':
                proxies.append(Proxy.parse_xml(child, source_location))
        ruleset = RuleSet.parse_xml(el, source_location)
        return cls(proxies, ruleset, source_location)

    @classmethod
    def parse_file(cls, filename):
        """Parse this from a filname"""
        file_url = filename_to_url(filename)
        tree = parse(filename, base_url=file_url)
        el = tree.getroot()
        tree.xinclude()
        return cls.parse_xml(el, file_url)

    def proxy_app(self, environ, start_response):
        """Implements the proxy, finding the matching `Proxy` object and
        forwarding the request on to that.
        """
        request = Request(environ)
        log = environ['deliverance.log']
        for index, proxy in enumerate(self.proxies):
            if proxy.editable:
                url = request.application_url + '/.deliverance/proxy-editor/%s/' % (index+1)
                name = proxy.editable_name
                if (url, name) not in log.edit_urls:
                    log.edit_urls.append((url, name))
            ## FIXME: obviously this is wonky:
            if proxy.match(request, None, None, log):
                try:
                    return proxy.forward_request(environ, start_response)
                except AbortProxy, e:
                    log.debug(
                        self, '<proxy> aborted (%s), trying next proxy' % e)
                    continue
                ## FIXME: should also allow for AbortTheme?
        log.error(
            self, 'No proxy matched the request; aborting with a 404 Not Found error')
        ## FIXME: better error handling would be nice:
        resp = exc.HTTPNotFound()
        return resp(environ, start_response)

    def rule_getter(self, get_resource, app, orig_req):
        """The rule getter for this (since the rules are parsed and intrinsic,
        this doesn't really *get* anything)"""
        return self.ruleset

    def application(self, environ, start_response):
        """The full application, that routes into the ruleset then out through
        the proxies itself.
        """
        req = Request(environ)
        log = SavingLogger(req, self.deliverator)
        req.environ['deliverance.log'] = log
        if req.path_info.startswith('/.deliverance/proxy-editor/'):
            req.path_info_pop()
            req.path_info_pop()
            return self.proxy_editor(environ, start_response)
        return self.deliverator(environ, start_response)

    def proxy_editor(self, environ, start_response):
        req = Request(environ)
        proxy = self.proxies[int(req.path_info_pop())-1]
        return proxy.edit_app(environ, start_response)
        

class Proxy(object):
    """Represents one ``<proxy>`` element.

    This both matches requests, applies transformations, then sends
    off the request.  It also does local file serving when proxying to
    ``file:`` URLs.
    """

    def __init__(self, match, dest,
                 request_modifications, response_modifications,
                 strip_script_name=True, keep_host=False,
                 source_location=None, classes=None, editable=False):
        self.match = match
        self.match.proxy = self
        self.dest = dest
        self.strip_script_name = strip_script_name
        self.keep_host = keep_host
        self.request_modifications = request_modifications
        self.response_modifications = response_modifications
        self.source_location = source_location
        self.classes = classes
        self.editable = editable

    def log_description(self, log=None):
        """The debugging description for use in log display"""
        parts = []
        if log is None:
            parts.append('&lt;proxy')
        else:
            parts.append('&lt;<a href="%s" target="_blank">proxy</a>' 
                         % log.link_to(self.source_location, source=True))
        ## FIXME: defaulting to true is bad
        if not self.strip_script_name:
            parts.append('strip-script-name="0"')
        if self.keep_host:
            parts.append('keep-host="1"')
        if self.editable:
            parts.append('editable="1"')
        parts.append('&gt;<br>\n')
        parts.append('&nbsp;' + self.dest.log_description(log))
        parts.append('<br>\n')
        if self.request_modifications:
            if len(self.request_modifications) > 1:
                parts.append('&nbsp;%i request modifications<br>\n' 
                             % len(self.request_modifications))
            else:
                parts.append('&nbsp;1 request modification<br>\n')
        if self.response_modifications:
            if len(self.response_modifications) > 1:
                parts.append('&nbsp;%i response modifications<br>\n' 
                             % len(self.response_modifications))
            else:
                parts.append('&nbsp;1 response modification<br>\n')
        parts.append('&lt;/proxy&gt;')
        return ' '.join(parts)

    @classmethod
    def parse_xml(cls, el, source_location):
        """Parse this document from an XML/etree element"""
        assert el.tag == 'proxy'
        match = ProxyMatch.parse_xml(el, source_location)
        dest = None
        request_modifications = []
        response_modifications = []
        strip_script_name = True
        keep_host = False
        editable = asbool(el.get('editable'))
        for child in el:
            if child.tag == 'dest':
                if dest is not None:
                    raise DeliveranceSyntaxError(
                        "You cannot have more than one <dest> tag (second tag: %s)"
                        % xml_tostring(child),
                        element=child, source_location=source_location)
                dest = ProxyDest.parse_xml(child, source_location)
            elif child.tag == 'transform':
                if child.get('strip-script-name'):
                    strip_script_name = asbool(child.get('strip-script-name'))
                if child.get('keep-host'):
                    keep_host = asbool(child.get('keep-host'))
                ## FIXME: error on other attrs
            elif child.tag == 'request':
                request_modifications.append(
                    ProxyRequestModification.parse_xml(child, source_location))
            elif child.tag == 'response':
                response_modifications.append(
                    ProxyResponseModification.parse_xml(child, source_location))
            elif child.tag is Comment:
                continue
            else:
                raise DeliveranceSyntaxError(
                    "Unknown tag in <proxy>: %s" % xml_tostring(child),
                    element=child, source_location=source_location)
        if editable:
            if not dest:
                ## FIXME: should this always be a test?
                raise DeliveranceSyntaxError("You must have a <dest> tag",
                                             element=el, source_location=source_location)
            try:
                href = uri_template_substitute(
                    dest.href, dict(here=posixpath.dirname(source_location)))
            except KeyError:
                raise DeliveranceSyntaxError(
                    'You can only use <proxy editable="1"> if you have a <dest href="..."> that only contains {here} (you have %s)'
                    % (dest.href))
            if not href.startswith('file:'):
                raise DeliveranceSyntaxError(
                    'You can only use <proxy editable="1"> if you have a <dest href="file:///..."> (you have %s)'
                    % (dest))
        classes = el.get('class', '').split() or None
        inst = cls(match, dest, request_modifications, response_modifications,
                   strip_script_name=strip_script_name, keep_host=keep_host,
                   source_location=source_location, classes=classes,
                   editable=editable)
        match.proxy = inst
        return inst

    def forward_request(self, environ, start_response):
        """Forward this request to the remote server, or serve locally.

        This also applies all the request and response transformations.
        """
        request = Request(environ)
        prefix = self.match.strip_prefix()
        if prefix:
            if prefix.endswith('/'):
                prefix = prefix[:-1]
            path_info = request.path_info
            if not path_info.startswith(prefix + '/') and not path_info == prefix:
                log = environ['deliverance.log']
                log.warn(
                    self, "The match would strip the prefix %r from the request "
                    "path (%r), but they do not match"
                    % (prefix + '/', path_info))
            else:
                request.script_name = request.script_name + prefix
                request.path_info = path_info[len(prefix):]
        log = request.environ['deliverance.log']
        for modifier in self.request_modifications:
            request = modifier.modify_request(request, log)
        if self.dest.next:
            raise AbortProxy
        dest = self.dest(request, log)
        log.debug(self, '<proxy> matched; forwarding request to %s' % dest)
        if self.classes:
            log.debug(self, 'Adding class="%s" to page' % ' '.join(self.classes))
            existing_classes = request.environ.setdefault('deliverance.page_classes', [])
            existing_classes.extend(self.classes)
        response, orig_base, proxied_base, proxied_url = self.proxy_to_dest(request, dest)
        for modifier in self.response_modifications:
            response = modifier.modify_response(request, response, orig_base, 
                                                proxied_base, proxied_url, log)
        return response(environ, start_response)

    def construct_proxy_request(self, request, dest):
        """ 
        returns a new Request object constructed by copying `request`
        and replacing its url with the url passed in as `dest`

        @raises TypeError if `dest` is a file:// url; this can be
        caught by the caller and handled accordingly
        """

        dest = url_normalize(dest)
        scheme, netloc, path, query, fragment = urlparse.urlsplit(dest)
        path = urllib.unquote(path)
        
        assert not fragment, (
            "Unexpected fragment: %r" % fragment)

        proxy_req = Request(request.environ.copy())

        proxy_req.path_info = path

        proxy_req.server_name = netloc.split(':', 1)[0]
        if ':' in netloc:
            proxy_req.server_port = netloc.split(':', 1)[1]
        elif scheme == 'http':
            proxy_req.server_port = '80'
        elif scheme == 'https':
            proxy_req.server_port = '443'
        elif scheme == 'file':
            raise TypeError ## FIXME: is TypeError too general?
        else:
            assert 0, "bad scheme: %r (from %r)" % (scheme, dest)
        if not self.keep_host:
            proxy_req.host = netloc

        proxy_req.query_string = query
        proxy_req.scheme = scheme

        proxy_req.headers['X-Forwarded-For'] = request.remote_addr
        proxy_req.headers['X-Forwarded-Scheme'] = request.scheme
        proxy_req.headers['X-Forwarded-Server'] = request.host

        ## FIXME: something with path? proxy_req.headers['X-Forwarded-Path']
        ## (now we are only doing it with strip_script_name)
        if self.strip_script_name:
            proxy_req.headers['X-Forwarded-Path'] = proxy_req.script_name
            proxy_req.script_name = ''

        return proxy_req

    def proxy_to_dest(self, request, dest):
        """Do the actual proxying, without applying any transformations"""
        # Not using request.copy because I don't want to copy wsgi.input:

        try:
            proxy_req = self.construct_proxy_request(request, dest)
        except TypeError:
            return self.proxy_to_file(request, dest)

        proxy_req.path_info += request.path_info

        if proxy_req.query_string and request.query_string:
            proxy_req.query_string = '%s&%s' % \
                (proxy_req.query_string, request.query_string)
        elif request.query_string:
            proxy_req.query_string = request.query_string

        proxy_req.accept_encoding = None
        try:
            resp = proxy_req.get_response(proxy_exact_request)
            if resp.status_int == 500:
                print 'Request:'
                print proxy_req
                print 'Response:'
                print resp
        except socket.error, e:
            ## FIXME: really wsgiproxy should handle this
            ## FIXME: which error?
            ## 502 HTTPBadGateway, 503 HTTPServiceUnavailable, 504 HTTPGatewayTimeout?
            if isinstance(e.args, tuple) and len(e.args) > 1:
                error = e.args[1]
            else:
                error = str(e)
            resp = exc.HTTPServiceUnavailable(
                'Could not proxy the request to %s:%s : %s' 
                % (proxy_req.server_name, proxy_req.server_port, error))

        dest = url_normalize(dest)
        orig_base = url_normalize(request.application_url)
        proxied_url = url_normalize('%s://%s%s' % (proxy_req.scheme, 
                                                   proxy_req.host,
                                                   proxy_req.path_qs))
        
        return resp, orig_base, dest, proxied_url

    def proxy_to_file(self, request, dest):
        """Handle local ``file:`` URLs"""
        orig_base = request.application_url
        ## FIXME: security restrictions here?
        assert dest.startswith('file:')
        if '?' in dest:
            dest = dest.split('?', 1)[0]
        filename = url_to_filename(dest)
        rest = posixpath.normpath(request.path_info)
        proxied_url = dest.lstrip('/') + '/' + urllib.quote(rest.lstrip('/'))
        ## FIXME: handle /->/index.html
        filename = filename.rstrip('/') + '/' + rest.lstrip('/')
        if os.path.isdir(filename):
            if not request.path.endswith('/'):
                new_url = request.path + '/'
                if request.query_string:
                    new_url += '?' + request.query_string
                resp = exc.HTTPMovedPermanently(location=new_url)
                return resp, orig_base, dest, proxied_url
            ## FIXME: configurable?  StaticURLParser?
            for base in ['index.html', 'index.htm']:
                if os.path.exists(os.path.join(filename, base)):
                    filename = os.path.join(filename, base)
                    break
            else:
                resp = exc.HTTPNotFound("There was no index.html file in the directory")
        if not os.path.exists(filename):
            resp = exc.HTTPNotFound("The file %s could not be found" % filename)
        else:
            app = FileApp(filename)
            # I don't really need a copied request here, because FileApp is so simple:
            resp = request.get_response(app)
        return resp, orig_base, dest, proxied_url

    def edit_app(self, environ, start_response):
        try:
            if not self.editable:
                raise exc.HTTPForbidden('This proxy is not editable="1"')
            if not edit_local_files(environ):
                raise exc.HTTPForbidden('Editing is forbidden')
            try:
                dest_href = uri_template_substitute(
                    self.dest.href, dict(here=posixpath.dirname(self.source_location)))
            except KeyError:
                raise exc.HTTPForbidden('Not a static location: %s' % self.dest.href)
            if not dest_href.startswith('file:/'):
                raise exc.HTTPForbidden('Not local: %s' % self.dest.href)
            filename = url_to_filename(dest_href)
            editor = Editor(base_dir=filename)
            return editor(environ, start_response)
        except exc.HTTPException, e:
            return e(environ, start_response)

    @property
    def editable_name(self):
        dest_href = self.dest.href
        base = posixpath.basename(dest_href)
        if not base:
            base = posixpath.basename(posixpath.dirname(dest_href))
        return base
        
class ProxyMatch(AbstractMatch):
    """Represents the request matching for <proxy> objects"""
    
    element_name = 'proxy'
    
    @classmethod
    def parse_xml(cls, el, source_location):
        """Parse this from XML/etree element"""
        ## FIXME: this should have a way of indicating what portion of the path to strip
        return cls(**cls.parse_match_xml(el, source_location))
    
    def debug_description(self):
        """The description used in AbstractMatch"""
        return '<proxy>'

    def log_context(self):
        """The context for log messages"""
        return self.proxy

    def strip_prefix(self):
        """The prefix that can be stripped off the request before forwarding it"""
        if self.path:
            return self.path.strip_prefix()
        return None

class ProxyDest(object):
    """Represents the ``<dest>`` element"""

    def __init__(self, href=None, pyref=None, next=False, source_location=None):
        self.href = href
        self.pyref = pyref
        self.next = next
        self.source_location = source_location

    @classmethod
    def parse_xml(cls, el, source_location):
        """Parse an instance from an etree XML element"""
        href = el.get('href')
        pyref = PyReference.parse_xml(
            el, source_location, 
            default_function='get_proxy_dest', default_objs=dict(AbortProxy=AbortProxy))
        next = asbool(el.get('next'))
        if next and (href or pyref):
            raise DeliveranceSyntaxError(
                'If you have a next="1" attribute you cannot also have an href '
                'or pyref attribute',
                element=el, source_location=source_location)
        return cls(href, pyref, next=next, source_location=source_location)

    def __call__(self, request, log):
        """Determine the destination given the request"""
        assert not self.next
        if self.pyref:
            if not execute_pyref(request):
                log.error(
                    self, "Security disallows executing pyref %s" % self.pyref)
            else:
                return self.pyref(request, log)
        ## FIXME: is this nesting really needed?
        ## we could just use HTTP_header keys...
        vars = NestedDict(request.environ, request.headers, 
                          dict(here=posixpath.dirname(self.source_location)))
        return uri_template_substitute(self.href, vars)

    def log_description(self, log=None):
        """The text to show when this is the context of a log message"""
        parts = ['&lt;dest']
        if self.href:
            if log is not None:
                parts.append('href="%s"' % html_quote(html_quote(self.href)))
            else:
                ## FIXME: definite security issue with the link through here:
                ## FIXME: Should this be source=True?
                parts.append(
                    'href="<a href="%s" target="_blank">%s</a>"' % 
                    (html_quote(log.link_to(self.href)), 
                     html_quote(html_quote(self.href))))
        if self.pyref:
            parts.append('pref="%s"' % html_quote(self.pyref))
        if self.next:
            parts.append('next="1"')
        parts.append('/&gt;')
        return ' '.join(parts)

class ProxyRequestModification(object):
    """Represents the ``<request>`` element in ``<proxy>``"""

    def __init__(self, pyref=None, header=None, content=None,
                 source_location=None):
        self.pyref = pyref
        self.header = header
        self.content = content
        self.source_location = source_location

    @classmethod
    def parse_xml(cls, el, source_location):
        """Parse an instance from an etree XML element"""
        assert el.tag == 'request'
        pyref = PyReference.parse_xml(
            el, source_location,
            default_function='modify_proxy_request', 
            default_objs=dict(AbortProxy=AbortProxy))
        header = el.get('header')
        content = el.get('content')
        ## FIXME: the misspelling is annoying :(
        if (not header and content) or (not content and header):
            raise DeliveranceSyntaxError(
                "If you provide a header attribute you must provide a "
                "content attribute, and vice versa",
                element=el, source_location=source_location)
        return cls(pyref, header, content,
                   source_location=source_location)
        
    def modify_request(self, request, log):
        """Apply the modification to the request"""
        if self.pyref:
            if not execute_pyref(request):
                log.error(
                    self, "Security disallows executing pyref %s" % self.pyref)
            else:
                result = self.pyref(request, log)
                if isinstance(result, dict):
                    request = Request(result)
                elif isinstance(result, Request):
                    request = result
        if self.header:
            request.headers[self.header] = self.content
        return request

class ProxyResponseModification(object):
    """Represents the ``<response>`` element in ``<proxy>``"""

    def __init__(self, pyref=None, header=None, content=None, rewrite_links=False,
                 source_location=None):
        self.pyref = pyref
        self.header = header
        self.content = content
        self.rewrite_links = rewrite_links
        self.source_location = source_location

    @classmethod
    def parse_xml(cls, el, source_location):
        """Create an instance from a parsed element"""
        assert el.tag == 'response'
        pyref = PyReference.parse_xml(
            el, source_location,
            default_function='modify_proxy_response', 
            default_objs=dict(AbortProxy=AbortProxy))
        header = el.get('header')
        content = el.get('content')
        if (not header and content) or (not content and header):
            raise DeliveranceSyntaxError(
                "If you provide a header attribute you must provide a content "
                "attribute, and vice versa",
                element=el, source_location=source_location)
        rewrite_links = asbool(el.get('rewrite-links'))
        return cls(pyref=pyref, header=header, content=content, 
                   rewrite_links=rewrite_links, source_location=source_location)

    _cookie_domain_re = re.compile(r'(domain="?)([a-z0-9._-]*)("?)', re.I)

    ## FIXME: instead of proxied_base/proxied_path, should I keep the
    ## modified request object?
    def modify_response(self, request, response, orig_base, proxied_base, 
                        proxied_url, log):
        """
        Modify the response however the user wanted.
        """
        # This might not have a trailing /:
        exact_proxied_base = proxied_base
        if not proxied_base.endswith('/'):
            proxied_base += '/'
        exact_orig_base = orig_base
        if not orig_base.endswith('/'):
            orig_base += '/'
        assert (proxied_url.startswith(proxied_base) 
                or proxied_url.split('?', 1)[0] == proxied_base[:-1]), (
            "Unexpected proxied_url %r, doesn't start with proxied_base %r"
            % (proxied_url, proxied_base))
        assert (request.url.startswith(orig_base) 
                or request.url.split('?', 1)[0] == orig_base[:-1]), (
            "Unexpected request.url %r, doesn't start with orig_base %r"
            % (request.url, orig_base))
        if self.pyref:
            if not execute_pyref(request):
                log.error(
                    self, "Security disallows executing pyref %s" % self.pyref)
            else:
                result = self.pyref(request, response, orig_base, proxied_base, 
                                    proxied_url, log)
                if isinstance(result, Response):
                    response = result
        if self.header:
            response.headers[self.header] = self.content
        if self.rewrite_links:
            def link_repl_func(link):
                """Rewrites a link to point to this proxy"""
                if link == exact_proxied_base:
                    return exact_orig_base
                if not link.startswith(proxied_base):
                    # External link, so we don't rewrite it
                    return link
                new = orig_base + link[len(proxied_base):]
                return new
            if response.content_type != 'text/html':
                log.debug(
                    self, 
                    'Not rewriting links in response from %s, because Content-Type is %s'
                    % (proxied_url, response.content_type))
            else:
                if not response.charset:
                    ## FIXME: maybe we should guess the encoding?
                    body = response.body
                else:
                    body = response.unicode_body
                body_doc = document_fromstring(body, base_url=proxied_url)
                body_doc.make_links_absolute()
                body_doc.rewrite_links(link_repl_func)
                response.body = tostring(body_doc)
            if response.location:
                ## FIXME: if you give a proxy like
                ## http://openplans.org, and it redirects to
                ## http://www.openplans.org, it won't be rewritten and
                ## that can be confusing -- it *shouldn't* be
                ## rewritten, but some better log message is required
                loc = urlparse.urljoin(proxied_url, response.location)
                loc = link_repl_func(loc)
                response.location = loc
            if 'set-cookie' in response.headers:
                cookies = response.headers.getall('set-cookie')
                del response.headers['set-cookie']
                for cook in cookies:
                    old_domain = urlparse.urlsplit(proxied_url)[1].lower()
                    new_domain = request.host.split(':', 1)[0].lower()
                    def rewrite_domain(match):
                        """Rewrites domains to point to this proxy"""
                        domain = match.group(2)
                        if domain == old_domain:
                            ## FIXME: doesn't catch wildcards and the sort
                            return match.group(1) + new_domain + match.group(3)
                        else:
                            return match.group(0)
                    cook = self._cookie_domain_re.sub(rewrite_domain, cook)
                    response.headers.add('set-cookie', cook)
        return response

class ProxySettings(object):
    """Represents the settings (``<server-settings>``) for the proxy
    """

    def __init__(self, server_host, execute_pyref=True, display_local_files=True,
                 edit_local_files=True,
                 dev_allow_ips=None, dev_deny_ips=None, dev_htpasswd=None, dev_users=None,
                 dev_expiration=0, dev_secret_file='/tmp/deliverance/devauth.txt',
                 source_location=None):
        self.server_host = server_host
        self.execute_pyref = execute_pyref
        self.display_local_files = display_local_files
        self.edit_local_files = edit_local_files
        self.dev_allow_ips = dev_allow_ips
        self.dev_deny_ips = dev_deny_ips
        self.dev_htpasswd = dev_htpasswd
        self.dev_expiration = dev_expiration
        self.dev_users = dev_users
        self.dev_secret_file = dev_secret_file
        self.source_location = source_location

    @classmethod
    def parse_xml(cls, el, source_location, environ=None, traverse=False):
        """Parse an instance from an etree XML element"""
        if traverse and el.tag != 'server-settings':
            try:
                el = el.xpath('//server-settings')[0]
            except IndexError:
                raise DeliveranceSyntaxError(
                    "There is no <server-settings> element",
                    element=el)
        if environ is None:
            environ = os.environ
        assert el.tag == 'server-settings'
        server_host = 'localhost:8080'
        ## FIXME: should these defaults be passed in:
        execute_pyref = True
        display_local_files = True
        edit_local_files = True
        dev_allow_ips = []
        dev_deny_ips = []
        dev_htpasswd = None
        dev_expiration = 0
        dev_users = {}
        dev_secret_file = os.path.join(tempfile.gettempdir(), 'deliverance', 'devauth.txt')
        for child in el:
            if child.tag is Comment:
                continue
            ## FIXME: should some of these be attributes?
            elif child.tag == 'server':
                server_host = cls.substitute(child.text, environ)
            elif child.tag == 'execute-pyref':
                execute_pyref = asbool(cls.substitute(child.text, environ))
            elif child.tag == 'dev-allow':
                dev_allow_ips.extend(cls.substitute(child.text, environ).split())
            elif child.tag == 'dev-deny':
                dev_deny_ips.extend(cls.substitute(child.text, environ).split())
            elif child.tag == 'dev-htpasswd':
                dev_htpasswd = os.path.join(os.path.dirname(url_to_filename(source_location)), cls.substitute(child.text, environ))
            elif child.tag == 'dev-expiration':
                dev_expiration = cls.substitute(child.text, environ)
                if dev_expiration:
                    dev_expiration = int(dev_expiration)
            elif child.tag == 'display-local-files':
                display_local_files = asbool(cls.substitute(child.text, environ))
            elif child.tag == 'edit-local-files':
                edit_local_files = asbool(cls.substitute(child.text, environ))
            elif child.tag == 'dev-user':
                username = cls.substitute(child.get('username', ''), environ)
                ## FIXME: allow hashed password?
                password = cls.substitute(child.get('password', ''), environ)
                if not username or not password:
                    raise DeliveranceSyntaxError(
                        "<dev-user> must have both a username and password attribute",
                        element=child)
                if username in dev_users:
                    raise DeliveranceSyntaxError(
                        '<dev-user username="%s"> appears more than once' % username,
                        element=el)
                dev_users[username] = password
            elif child.tag == 'dev-secret-file':
                dev_secret_file = cls.substitute(child.text, environ)
            else:
                raise DeliveranceSyntaxError(
                    'Unknown element in <server-settings>: <%s>' % child.tag,
                    element=child)
        if dev_users and dev_htpasswd:
            raise DeliveranceSyntaxError(
                "You can use <dev-htpasswd> or <dev-user>, but not both",
                element=el)
        if not dev_users and not dev_htpasswd:
            ## FIXME: not sure this is the best way to warn
            print 'Warning: no <dev-users> or <dev-htpasswd>; logging is inaccessible'
        ## FIXME: add a default allow_ips of 127.0.0.1?
        return cls(server_host, execute_pyref=execute_pyref, 
                   display_local_files=display_local_files,
                   edit_local_files=edit_local_files,
                   dev_allow_ips=dev_allow_ips, dev_deny_ips=dev_deny_ips, 
                   dev_users=dev_users, dev_htpasswd=dev_htpasswd,
                   dev_expiration=dev_expiration,
                   source_location=source_location,
                   dev_secret_file=dev_secret_file)

    @classmethod
    def parse_file(cls, filename):
        """Parse from a file"""
        file_url = filename_to_url(filename)
        tree = parse(filename, base_url=file_url)
        el = tree.getroot()
        tree.xinclude()
        return cls.parse_xml(el, file_url, traverse=True)

    @property
    def host(self):
        """The host to attach to (not the port)"""
        return self.server_host.split(':', 1)[0]

    @property
    def port(self):
        """The port to attach to (an integer)"""
        if ':' in self.server_host:
            return int(self.server_host.split(':', 1)[1])
        else:
            return 80

    @property
    def base_url(self):
        """The base URL that you can browse to"""
        host = self.host
        if host == '0.0.0.0' or not host:
            host = '127.0.0.1'
        if self.port != 80:
            host += ':%s' % self.port
        return 'http://' + host

    @staticmethod
    def substitute(template, environ):
        """Substitute the given template with the given environment"""
        if environ is None:
            return template
        return string.Template(template).substitute(environ)

    def middleware(self, app):
        """
        Wrap the given application in an appropriate DevAuth and Security instance
        """
        from devauth import DevAuth, convert_ip_mask
        from deliverance.security import SecurityContext
        if self.dev_users:
            password_checker = self.check_password
        else:
            password_checker = None
        app = SecurityContext.middleware(app, execute_pyref=self.execute_pyref,
                                         display_local_files=self.display_local_files,
                                         edit_local_files=self.edit_local_files)
        if password_checker is None and not self.dev_htpasswd:
            ## FIXME: warn here?
            return app
        app = DevAuth(
            app,
            allow=convert_ip_mask(self.dev_allow_ips),
            deny=convert_ip_mask(self.dev_deny_ips),
            password_file=self.dev_htpasswd,
            password_checker=password_checker,
            expiration=self.dev_expiration,
            login_mountpoint='/.deliverance',
            secret_file=self.dev_secret_file)
        return app

    def check_password(self, username, password):
        """Password checker for use in `DevAuth`"""
        assert self.dev_users
        return self.dev_users.get(username) == password

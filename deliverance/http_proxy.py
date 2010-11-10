from deliverance.util.urlnormalize import url_normalize
import socket
from wsgiproxy.exactproxy import proxy_exact_request
from lxml.html import document_fromstring, tostring
import re
import urllib
import urlparse
from webob import Request
import logging

class Proxy(object):

    rewrite_links = True 
    keep_host = False
    strip_script_name = True

    def __init__(self, dest):
        self._dest = dest

    def dest(self, request):
        return self._dest

    def log(self, request, msg, level='warn'):
        pass

    def strip_prefix(self):
        pass

    def __call__(self, environ, start_response):
        """Forward this request to the remote server, or serve locally.

        This also applies all the request and response transformations.
        """
        request, original_script_name, original_path_info = \
            self.prepare_request(environ)

        response, orig_base, proxied_base, proxied_url = self.proxy_to_dest(
            request, self.dest(request))

        if self.rewrite_links:
            response = self.rewritten(request, response, 
                                      orig_base, proxied_base, proxied_url)

        return response(environ, start_response)

    def prepare_request(self, environ):
        request = Request(environ)
        original_script_name = request.script_name
        original_path_info = request.path_info
        prefix = self.strip_prefix()
        if prefix:
            if prefix.endswith('/'):
                prefix = prefix[:-1]
            path_info = request.path_info
            if not path_info.startswith(prefix + '/') and not path_info == prefix:
                self.log(request, 
                         "The match would strip the prefix %r from the request "
                         "path (%r), but they do not match"
                         % (prefix + '/', path_info))
            else:
                request.script_name = request.script_name + prefix
                request.path_info = path_info[len(prefix):]

        return request, original_script_name, original_path_info

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
        proxy_req = self.construct_proxy_request(request, dest)

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

    _cookie_domain_re = re.compile(r'(domain="?)([a-z0-9._-]*)("?)', re.I)

    def rewritten(self, request, response, orig_base, proxied_base, proxied_url):

        if proxied_base is not None and proxied_url is not None:
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
            self.log(request,
                     'Not rewriting links in response from %s, because Content-Type is %s'
                     % (proxied_url, response.content_type),
                     'debug')
        else:
            if not response.charset:
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

if __name__ == '__main__':
    req = Request.blank("http://nytimes.com/about")
    app = Proxy("http://www.google.com")
    resp = req.get_response(app)
    print resp.location
    

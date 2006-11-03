"""
Takes a response (headers + content) and relocates it, changing domain
names and paths.
"""
import fixuplinks
import urlparse
from paste.request import construct_url
from paste.response import header_value

def relocate_response(headers, content, base_href, old_href, new_href):
    """
    Takes headers and content, and replaces all instances of old_href
    with new_href.  Returns (new_headers, new_content)
    """
    new_headers = relocate_headers(headers, base_href, old_href, new_href)
    new_content = relocate_content(content, base_href, old_href, new_href)
    return new_headers, new_content

def relocate_headers(headers, base_href, old_href, new_href):
    new_headers = []
    for name, value in headers:
        if name.lower() == 'location':
            value = relocate_href(value, base_href, old_href, new_href)
        new_headers.append((name, value))
    return new_headers

def relocate_content(content, base_href, old_href, new_href):
    def sub_link(href):
        return relocate_href(href, base_href, old_href, new_href)
    return fixuplinks.fixup_text_links(content, sub_link)

def relocate_href(href, base_href, old_href, new_href):
    real_href = urlparse.urljoin(base_href, href)
    if not real_href.startswith(old_href):
        return href
    return new_href + real_href[len(old_href):]

class RelocateMiddleware(object):

    def __init__(self, app, old_href):
        self.app = app
        if old_href.endswith(':80'):
            old_href = old_href[:-3]
        self.old_href = old_href

    def __call__(self, environ, start_response):
        new_href = construct_url(environ, path_info='')
        base_href = construct_url(environ)
        skipped = []
        written = []
        stat_headers = []
        def repl_start_response(status, headers, exc_info=None):
            headers = relocate_headers(headers, base_href, self.old_href, new_href)
            content_type = header_value(headers, 'content-type')
            if not content_type or not content_type.startswith('text/html'):
                skipped.append(True)
                return start_response(status, headers, exc_info)
            stat_headers[:] = [status, headers]
            return written.append
        app_iter = self.app(environ, repl_start_response)
        if skipped:
            return app_iter
        start_response(*stat_headers)
        try:
            for chunk in app_iter:
                written.append(chunk)
        finally:
            if hasattr(app_iter, 'close'):
                app_iter.close()
        content = ''.join(written)
        content = relocate_content(content, base_href, self.old_href, new_href)
        return [content]

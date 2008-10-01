"""Normalize URLs"""
import urlparse
import urllib
import re

def url_normalize(url):
    """Normalizes the quoting of URLs, quoting any characters that should
    be quoted (but not double-quoting already quoted characters)"""
    scheme, netloc, path, query, fragment = urlparse.urlsplit(url)
    scheme = scheme.lower()
    if ':' in netloc:
        host, port = netloc.split(':', 1)
        if scheme == 'http' and port == '80':
            netloc = host
        elif scheme == 'https' and port == '443':
            netloc = host
    netloc = netloc.lower()
    path = _quote_special(path)
    if query:
        path += '?' + query
    if fragment:
        path += '#' + fragment
    result = '%s://%s%s' % (scheme, netloc, path)
    return result

_slash_re = re.compile(r'%2f', re.I)

def _quote_special(path):
    """Quotes any characters in the path that should be quoted, unquotes
    characters that don't need to be quoted.  Also % quoting is
    upper-cased"""
    parts = [_quote_special_part(part)
             for part in _slash_re.split(path)]
    return '%2F'.join(parts)

_percent_re = re.compile(r'%[0-9a-f][0-9a-f]', re.I)

def _quote_special_part(part):
    return urllib.quote(urllib.unquote(part))
    

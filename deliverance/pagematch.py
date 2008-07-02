"""
Handles the <match> tag and matching requests and responses against these patterns.
"""

from deliverance.exceptions import DeliveranceSyntaxError, AbortTheme
from deliverance.stringmatch import compile_matcher, compile_header_matcher
from deliverance.util.converters import asbool, html_quote

__all__ = ['MatchSyntaxError', 'Match']

class Match(object):
    """
    Represents the <match> tags.

    You can call this object to apply the match
    """

    def __init__(self, classes, path=None, domain=None,
                 request_header=None, response_header=None, environ=None,
                 abort=False, last=False, source_location=None):
        self.classes = classes
        self.path = path
        self.domain = domain
        self.request_header = request_header
        self.response_header = response_header
        self.environ = environ
        self.abort = abort
        self.last = last
        self.source_location = source_location
    
    @classmethod
    def parse_xml(cls, el, source_location):
        """
        Creates an instance of Match from the given parsed XML element.
        """
        assert (el.tag == 'match'
                or el.tag == 'rule')
        classes = el.get('class', '').split()
        abort = asbool(el.get('abort'))
        if not abort and not classes:
            ## FIXME: source location
            raise DeliveranceSyntaxError(
                "You must provide some classes in the class attribute")
        if abort and classes:
            ## FIXME: source location
            raise DeliveranceSyntaxError(
                'You cannot provide both abort="1" and class="%s"'
                % (' '.join(classes)))
        path = cls._parse_attr(el, 'path', default='path')
        domain = cls._parse_attr(el, 'domain', default='wildcard')
        request_header = cls._parse_attr(el, 'request-header', default='exact', header=True)
        response_header = cls._parse_attr(el, 'response-header', default='exact', header=True)
        environ = cls._parse_attr(el, 'environ', default='exact', header=True)
        last = asbool(el.get('last'))
        return cls(
            classes,
            path=path,
            domain=domain,
            request_header=request_header,
            response_header=response_header,
            environ=environ,
            abort=abort,
            last=last,
            source_location=source_location)

    @staticmethod
    def _parse_attr(el, attr, default=None, header=False):
        """
        Compiles a single string pattern
        """
        value = el.get(attr)
        if value is None:
            return None
        if header:
            return compile_header_matcher(value, default)
        else:
            return compile_matcher(value, default)

    def __unicode__(self):
        parts = [u'<match']
        if self.classes:
            parts.append(u'class="%s"' % html_quote(' '.join(self.classes)))
        for attr, value in [
            ('path', self.path),
            ('domain', self.domain),
            ('request-header', self.request_header),
            ('response-header', self.response_header),
            ('environ', self.environ)]:
            if value:
                parts.append(u'%s="%s"' % (attr, html_quote(unicode(self.path))))
        if self.abort:
            parts.append(u'abort="1"')
        if self.last:
            parts.append(u'last="1"')
        parts.append(u'/>')
        return ' '.join(parts)

    def __str__(self):
        return unicode(self).encode('utf8')

    def __call__(self, request, response_headers, log):
        """
        Checks this match against the given request and response_headers object.

        `response_headers` should be a case-insensitive dictionary.  `request` should be a
        :class:webob.Request object.
        """
        result = True
        if self.abort:
            class_name = 'abort'
        elif len(self.classes) > 1:
            class_name = '(%s)' % ' '.join(self.classes)
        else:
            class_name = self.classes[0]
        if self.path:
            if not self.path(request.path):
                log.debug(self, 'Skipping class %s because request URL (%s) does not match path="%s"',
                          class_name, request.path, self.path)
                return False
        if self.domain:
            host = request.host.split(':', 1)[0]
            if not self.domain(host):
                log.debug(self, 'Skipping class %s because request domain (%s) does not match domain="%s"',
                          class_name, host, self.domain)
                return False
        if self.request_header:
            result, headers = self.request_header(request.headers)
            if not result:
                log.debug(self, 'Skipping class %s because request headers %s do not match request-header="%s"',
                          class_name, ', '.join(headers), self.request_header)
                return False
        if self.response_header:
            result, headers = self.response_header(response_headers)
            if not result:
                ## FIXME: maybe distinguish <meta> headers and real headers?
                log.debug(self, 'Skipping class %s because the response headers %s do not match response-header="%s"',
                          class_name, ', '.join(headers), self.response_header)
                return False
        if self.environ:
            result, keys = self.environ(request.environ)
            if not result:
                log.debug(self, 'Skipping class %s because the request environ (keys %s) did not match environ="%s"',
                          class_name, ', '.join(keys), self.environ)
                return False
        return True

def run_matches(matchers, request, response_headers, log):
    """
    Runs all the match objects in matchers, returning the list of matched classes.
    """
    results = []
    for matcher in matchers:
        if matcher(request, response_headers, log):
            if matcher.abort:
                log.debug(matcher, '<match> matched request, aborting')
                raise AbortTheme('<match> matched request, aborting')
            log.debug(matcher, '<match> matched request, adding classes %s',
                      ', '.join(matcher.classes))
            for item in matcher.classes:
                if item not in results:
                    results.append(item)
            if matcher.last:
                log.debug(matcher, 'Stopping matches (skipping %i matches)',
                          len(matchers) - matchers.index(matcher) - 1)
                return results
    return results

"""
Handles the <match> tag and matching requests and responses against these patterns.
"""

from deliverance.exceptions import DeliveranceSyntaxError, AbortTheme
from deliverance.stringmatch import compile_matcher, compile_header_matcher
from deliverance.util.converters import asbool, html_quote
from deliverance.pyref import PyReference
from deliverance.security import execute_pyref

class AbstractMatch(object):
    """
    Represents the <match> tags.

    You can call this object to apply the match
    """
    
    # Subclasses must override:
    element_name = None

    def __init__(self, path=None, domain=None,
                 request_header=None, response_header=None, environ=None,
                 pyref=None, source_location=None):
        ## FIXME: this should add response_status
        self.path = path
        self.domain = domain
        self.request_header = request_header
        self.response_header = response_header
        self.environ = environ
        self.pyref = pyref
        self.source_location = source_location

    
    @classmethod
    def parse_match_xml(cls, el, source_location):
        """
        Parses out the match-related arguments
        """
        path = cls._parse_attr(el, 'path', default='path')
        domain = cls._parse_attr(el, 'domain', default='wildcard-insensitive')
        request_header = cls._parse_attr(el, 'request-header', default='exact', 
                                         header=True)
        response_header = cls._parse_attr(el, 'response-header', default='exact', 
                                          header=True)
        environ = cls._parse_attr(el, 'environ', default='exact', header=True)
        pyref = PyReference.parse_xml(
            el, source_location=source_location,
            default_function='match_request',
            default_objs=dict(AbortTheme=AbortTheme))
        return dict(
            path=path,
            domain=domain,
            request_header=request_header,
            response_header=response_header,
            environ=environ,
            pyref=pyref,
            source_location=source_location)

    match_attrs = [
        'path', 'domain', 'request-header', 'response-header', 'environ', 'pyref']

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
        assert self.element_name, (
            "You must set element_name in subclasses")
        parts = [u'<%s' % self.element_name]
        parts.extend(self._uni_early_args())
        for attr, value in [
            ('path', self.path),
            ('domain', self.domain),
            ('request-header', self.request_header),
            ('response-header', self.response_header),
            ('environ', self.environ)]:
            if value:
                parts.append(u'%s="%s"' % (attr, html_quote(unicode(value))))
        if self.pyref:
            parts.append(unicode(self.pyref))
        parts.extend(self._uni_late_args())
        parts.append(u'/>')
        return ' '.join(parts)

    def _uni_early_args(self):
        """Override to change the unicode() of this object"""
        return []

    def _uni_late_args(self):
        """Override to change the unicode() of this object"""
        return []

    def __str__(self):
        return unicode(self).encode('utf8')

    def debug_description(self):
        """Override to control the way this object displays in debugging contexts"""
        raise NotImplementedError

    def log_context(self):
        """The return value is used for the context to ``log.debug()`` etc methds"""
        return self

    def __call__(self, request, resp, response_headers, log):
        """
        Checks this match against the given request and
        response_headers object.

        `response_headers` should be a case-insensitive dictionary.
        `request` should be a :class:webob.Request object.
        """
        result = True
        debug_name = self.debug_description()
        debug_context = self.log_context()
        if self.path:
            if not self.path(request.path):
                log.debug(
                    debug_context, 'Skipping %s because request URL (%s) does not '
                    'match path="%s"',
                    debug_name, request.path, self.path)
                return False
        if self.domain:
            host = request.host.split(':', 1)[0]
            if not self.domain(host):
                log.debug(
                    debug_context, 'Skipping %s because request domain (%s) does '
                    'not match domain="%s"',
                    debug_name, host, self.domain)
                return False
        if self.request_header:
            result, headers = self.request_header(request.headers)
            if not result:
                log.debug(
                    debug_context, 'Skipping %s because request headers %s do not '
                    'match request-header="%s"',
                    debug_name, ', '.join(headers), self.request_header)
                return False
        if self.response_header:
            result, headers = self.response_header(response_headers)
            if not result:
                header_debug = []
                for header in headers:
                    header_debug.append('%s: %s' % (header, response_headers.get(header, '(empty)')))
                ## FIXME: maybe distinguish <meta> headers and real headers?
                log.debug(
                    debug_context, 'Skipping %s because the response headers %s '
                    'do not match response-header="%s"',
                    debug_name, ', '.join(header_debug), self.response_header)
                return False
        if self.environ:
            result, keys = self.environ(request.environ)
            if not result:
                log.debug(
                    debug_context, 'Skipping %s because the request environ (keys %s) '
                    'did not match environ="%s"',
                    debug_name, ', '.join(keys), self.environ)
                return False
        if self.pyref:
            if not execute_pyref(request):
                log.error(
                    self, "Security disallows executing pyref %s")
            else:
                result = self.pyref(request, resp, response_headers, log)
                if not result:
                    log.debug(
                        debug_context, 
                        'Skipping %s because the reference <%s> returned false',
                        debug_name, self.pyref)
                    return False
                if isinstance(result, basestring):
                    result = result.split()
                if isinstance(result, (list, tuple)):
                    return getattr(self, 'classes', []) + list(result)
        return getattr(self, 'classes', None) or True

class Match(AbstractMatch):
    """
    Represents the ``<match>`` page-class applicator.
    """

    element_name = 'match'

    def __init__(self, classes=None, abort=False, last=False, **kw):
        super(Match, self).__init__(**kw)
        self.classes = classes
        self.abort = abort
        self.last = last

    @classmethod
    def parse_xml(cls, el, source_location):
        """
        Parses the <match> element into a match object
        """
        matchargs = cls.parse_match_xml(el, source_location)
        assert el.tag == cls.element_name
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
        last = asbool(el.get('last'))
        return cls(
            classes=classes, abort=abort, last=last, **matchargs)

    def _uni_early_args(self):
        """Add the extra args <match> uses"""
        if self.classes:
            return [u'class="%s"' % html_quote(' '.join(self.classes))]
        else:
            return []

    def _uni_late_args(self):
        """Add the extra args <match> uses"""
        parts = []
        if self.abort:
            parts.append(u'abort="1"')
        if self.last:
            parts.append(u'last="1"')
        return parts

    def debug_description(self):
        """Description for debugging messages"""
        if self.abort:
            return 'abort'
        else:
            return 'class="%s"' % ' '.join(self.classes)

class ClientsideMatch(AbstractMatch):
    """
    Represents <clientside>
    """

    element_name = 'clientside'

    ## FIXME: only request matches are applicable
    @classmethod
    def parse_xml(cls, el, source_location):
        matchargs = cls.parse_match_xml(el, source_location)
        return cls(**matchargs)

    def debug_description(self):
        """Description for debugging messages"""
        return ''

def run_matches(matchers, request, resp, response_headers, log):
    """
    Runs all the match objects in matchers, returning the list of matched classes.
    """
    results = []
    for matcher in matchers:
        classes = matcher(request, resp, response_headers, log)
        if classes:
            if matcher.abort:
                log.debug(matcher, '<match> matched request, aborting')
                raise AbortTheme('<match> matched request, aborting')
            log.debug(matcher, '<match> matched request, adding classes %s',
                      ', '.join(classes))
            for item in classes:
                if item not in results:
                    results.append(item)
            if matcher.last:
                log.debug(matcher, 'Stopping matches (skipping %i matches)',
                          len(matchers) - matchers.index(matcher) - 1)
                return results
    return results

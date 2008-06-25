import fnmatch
import re

__all__ = ['compile_matcher', 'compile_header_matcher', 'MatchSyntaxError']

_prefix_re = re.compile(r'^([a-z_-]+):', re.I)

def compile_matcher(s, default=None):
    match = _prefix_re.search(s)
    if not match:
        if default is None:
            ## FIXME: show possible names?
            raise MatchSyntaxError(
                "You must provide a match type (like type:) in the pattern %r"
                % s)
        type = default
        pattern = s
    else:
        type = match.group(1).lower()
        pattern = s[match.end():]
    if type not in _matches:
        ## FIXME: show possible names?
        raise MatchSyntaxError(
            "The type %r is not valid"
            % (type + ':'))
    return _matches[type](pattern)

def compile_header_matcher(s, default='exact'):
    if ':' not in s:
        raise MatchSyntaxError(
            "A header match must be like 'Header: pattern'; you have no header in %r"
            % s)
    header, pattern = s.split(':', 1)
    header = header.strip()
    pattern = pattern.lstrip()
    pattern = compile_matcher(pattern, default)
    if '*' in header:
        return HeaderWildcardMatcher(header, pattern)
    else:
        return HeaderMatcher(header, pattern)

class MatchSyntaxError(Exception):
    """
    Raised if you have an invalid expression in a matcher
    """

_matches = {}

def _add_matcher(cls):
    _matches[cls.name] = cls

class Matcher(object):

    name = None

    def __init__(self, pattern):
        self.pattern = pattern

    def __call__(self, s):
        raise NotImplementedError

    def __unicode__(self):
        return '%s:%s' % (self.name, self.pattern)

    def __str__(self):
        return str(unicode(self))
    
    def __repr__(self):
        return '<%s %s>' % (self.__class__.__name__, str(self))

class WildcardMatcher(Matcher):

    name = 'wildcard'

    def __init__(self, pattern):
        super(WildcardMatcher, self).__init__(pattern)
        self.compiled = re.compile(fnmatch.translate(pattern))

    def __call__(self, s):
        return bool(self.compiled.match(s))

_add_matcher(WildcardMatcher)

class WildcardInsensitiveMatcher(Matcher):

    name = 'wildcard-insensitive'

    def __init__(self, pattern):
        super(WildcardInsensitiveMatcher, self).__init__(pattern)
        self.compiled = re.compile(fnmatch.translate(pattern), re.I)

    def __call__(self, s):
        return bool(self.compiled.match(s))

_add_matcher(WildcardInsensitiveMatcher)

class RegexMatcher(Matcher):

    name = 'regex'

    def __init__(self, pattern):
        super(RegexMatcher, self).__init__(pattern)
        try:
            self.compiled = re.compile(pattern)
        except re.error, e:
            raise MatchSyntaxError(
                "Invalid regular expression %r: %s"
                % (pattern, e))
    
    def __call__(self, s):
        return bool(self.compiled.match(s))
            
_add_matcher(RegexMatcher)

class PathMatcher(Matcher):

    name = 'path'

    def __init__(self, pattern):
        if not pattern.endswith('/'):
            pattern += '/'
        super(PathMatcher, self).__init__(pattern)

    def __call__(self, s):
        return (s == self.pattern[:-1]
                or s.startswith(self.pattern))

_add_matcher(PathMatcher)

class ExactMatcher(Matcher):

    name = 'exact'

    def __call__(self, s):
        return s == self.pattern

_add_matcher(ExactMatcher)
        
class ExactInsensitiveMatcher(Matcher):
    
    name = 'exact-insensitive'

    def __call__(self, s):
        return s.lower() == self.pattern.lower()

_add_matcher(ExactInsensitiveMatcher)

class ContainsMatcher(Matcher):

    name = 'contains'

    def __call__(self, s):
        return self.pattern in s

_add_matcher(ContainsMatcher)

class ContainsInsensitiveMatcher(Matcher):

    name = 'contains-insensitive'

    def __call__(self, s):
        return self.pattern.lower() in s.lower()

_add_matcher(ContainsInsensitiveMatcher)

class HeaderMatcher(object):

    def __init__(self, header, pattern):
        self.header = header
        self.pattern = pattern

    def __call__(self, headers):
        return self.pattern(headers.get(self.header, ''))

    def __unicode__(self):
        return u'%s: %s' % (self.header, self.pattern)

class HeaderWildcardMatcher(object):

    def __init__(self, header, pattern):
        self.header = header
        self.header_re = re.compile(fnmatch.translate(header), re.I)
        self.pattern = pattern

    def __call__(self, headers):
        matches = self.header_re.match
        for key in headers:
            if matches(key):
                if self.pattern(headers[key]):
                    return True
        return False

    def __unicode__(self):
        return u'%s: %s' % (self.header, self.pattern)

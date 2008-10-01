"""
Represents the string and header matching that is used to determine page classes.
"""

import fnmatch
import re
from deliverance.util.converters import asbool

__all__ = ['compile_matcher', 'compile_header_matcher', 'MatchSyntaxError']

_prefix_re = re.compile(r'^([a-z_-]+):', re.I)

def compile_matcher(s, default=None):
    """
    Compiles the match string to a match object.

    Match objects are callable objects that return a boolean.
    """
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
        pattern = s[match.end():].lstrip()
    if type not in _matches:
        ## FIXME: show possible names?
        raise MatchSyntaxError(
            "The type %r is not valid"
            % (type + ':'))
    return _matches[type](pattern)

def compile_header_matcher(s, default='exact'):
    """
    Compiles the match header string to a match object.

    Unlike simple match objects, these match against a dictionary of headers.

    This also applies the the environ dictionary.  Case-sensitivity is
    handled by the dictionary, not the matcher.
    """
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
    """Registers a matcher"""
    _matches[cls.name] = cls

class Matcher(object):
    # Abstract base class for matchers

    name = None

    def strip_prefix(self):
        """
        String prefix to strip from a matched string
        """
        return None

    def __init__(self, pattern):
        self.pattern = pattern

    def __call__(self, s):
        raise NotImplementedError

    def __unicode__(self):
        return '%s:%s' % (self.name, self.pattern)

    def __str__(self):
        return unicode(self).encode('utf8')
    
    def __repr__(self):
        return '<%s %s>' % (self.__class__.__name__, str(self))

class WildcardMatcher(Matcher):
    """
    Matches a value against a pattern that may contain ``*`` wildcards.
    """

    name = 'wildcard'

    def __init__(self, pattern):
        super(WildcardMatcher, self).__init__(pattern)
        self.compiled = re.compile(fnmatch.translate(pattern))

    def __call__(self, s):
        return bool(self.compiled.match(s))

_add_matcher(WildcardMatcher)

class WildcardInsensitiveMatcher(Matcher):
    """
    Matches a value, ignoring case, against a pattern with wildcards.
    """

    name = 'wildcard-insensitive'

    def __init__(self, pattern):
        super(WildcardInsensitiveMatcher, self).__init__(pattern)
        self.compiled = re.compile(fnmatch.translate(pattern), re.I)

    def __call__(self, s):
        return bool(self.compiled.match(s))

_add_matcher(WildcardInsensitiveMatcher)

class RegexMatcher(Matcher):
    """
    Matches a value against a regular expression.
    """

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
    """
    Matches a value against a path.  This checks prefixes, but also
    only matches /-delimited segments.
    """

    name = 'path'

    def __init__(self, pattern):
        if not pattern.endswith('/'):
            pattern += '/'
        super(PathMatcher, self).__init__(pattern)

    def __call__(self, s):
        return (s == self.pattern[:-1]
                or s.startswith(self.pattern))

    def strip_prefix(self):
        """The prefix that can be stripped (path: actually can do this)"""
        return self.pattern

_add_matcher(PathMatcher)

class ExactMatcher(Matcher):
    """
    Matches a string exactly.
    """

    name = 'exact'

    def __call__(self, s):
        return s == self.pattern

    def strip_prefix(self):
        return self.pattern

_add_matcher(ExactMatcher)
        
class ExactInsensitiveMatcher(Matcher):
    """
    Matches a string exactly, but ignoring case.
    """
    
    name = 'exact-insensitive'

    def __call__(self, s):
        return s.lower() == self.pattern.lower()

_add_matcher(ExactInsensitiveMatcher)

class ContainsMatcher(Matcher):
    """
    Matches if the value contains the pattern.
    """

    name = 'contains'

    def __call__(self, s):
        return self.pattern in s

_add_matcher(ContainsMatcher)

class ContainsInsensitiveMatcher(Matcher):
    """
    Matches if the value contains the pattern, ignoring case.
    """

    name = 'contains-insensitive'

    def __call__(self, s):
        return self.pattern.lower() in s.lower()

_add_matcher(ContainsInsensitiveMatcher)

class BooleanMatcher(Matcher):
    """
    Matches according to a boolean true/falseness of a value
    """
    
    name = 'boolean'

    def __init__(self, pattern):
        pattern = pattern.strip()
        super(BooleanMatcher, self).__init__(pattern)
        if pattern.lower() == 'not':
            pattern = 'false'
        if not pattern:
            pattern = 'true'
        self.boolean = asbool(pattern)

    def __call__(self, s):
        try:
            value = asbool(s)
        except ValueError:
            value = False
        if self.boolean:
            return value
        else:
            return not value

_add_matcher(BooleanMatcher)

class HeaderMatcher(object):
    """
    Matches simple "Header: pattern".  Does not match wildcard headers.
    """

    def __init__(self, header, pattern):
        self.header = header
        self.pattern = pattern

    def __call__(self, headers):
        return self.pattern(headers.get(self.header, '')), [self.header]

    def __unicode__(self):
        return u'%s: %s' % (self.header, self.pattern)

    def __str__(self):
        return unicode(self).encode('utf8')

class HeaderWildcardMatcher(object):
    """
    Matches "Header*: pattern", where the header contains a wildcard.
    """

    def __init__(self, header, pattern):
        self.header = header
        self.header_re = re.compile(fnmatch.translate(header), re.I)
        self.pattern = pattern

    def __call__(self, headers):
        matches = self.header_re.match
        matched = []
        for key in headers:
            if matches(key):
                matched.append(key)
                if self.pattern(headers[key]):
                    return True, [key]
        return False, matched

    def __unicode__(self):
        return u'%s: %s' % (self.header, self.pattern)

    def __str__(self):
        return unicode(self).encode('utf8')

"""
Implements the element selection; XPath, CSS, and the modifiers on
those selections.
"""

import re
from lxml.etree import XPath
from lxml.cssselect import CSSSelector
from deliverance.exceptions import DeliveranceSyntaxError

type_re = re.compile(r'^(elements?|children|tag|attributes?):')
type_map = dict(element='elements', attribute='attributes')
attributes_re = re.compile(r'^attributes[(]([a-zA-Z0-9_,-]+)[)]:')

class Selector(object):
    """
    Represents one selection attribute

    A selector contains multiple sub-selectors; this level combines
    those from the || (cascading) operator.
    """

    def __init__(self, major_type, attributes, selectors):
        self.major_type = major_type
        self.attributes = attributes
        self.selectors_source = selectors
        self.selectors = [self.compile_selector(selector, default_type=major_type)
                          for selector in selectors]

    @classmethod
    def parse(cls, expr):
        """
        Parses one string expression, returning an instance of this class.
        """
        major_type, attributes, expr = cls.parse_prefix(expr)
        selectors = [e.strip()
                     for e in expr.split('||')]
        return cls(major_type, attributes, selectors)

    @staticmethod
    def parse_prefix(expr, default_type='elements'):
        """
        Parses the elements:, etc, prefix.

        Returns (type, attributes, rest_expr)
        """
        assert isinstance(expr, basestring), "Bad value for expr: %r" % expr
        match = type_re.match(expr)
        if match:
            major_type = match.group(1)
            major_type = type_map.get(major_type, major_type)
            rest_expr = expr[match.end():]
            return (major_type, None, rest_expr)
        else:
            match = attributes_re.match(expr)
            if match:
                attributes = [name.strip() for name in match.group(1).split(',') 
                              if name.strip()]
                rest_expr = expr[match.end():]
                return ('attributes', attributes, rest_expr)
        return (default_type, None, expr)

    @staticmethod
    def types_compatible(type1, type2):
        """
        When multiple types appear (separated with ||) this tests if
        they are compatible with each other.

        Only ``children`` and ``elements`` are compatible with each
        other; in all other cases you must use the same type.
        """
        if type1 in ('children', 'elements'):
            return type2 in ('children', 'elements')
        else:
            return type1 == type2
            
    def __str__(self):
        return unicode(self).encode('utf8')

    def compile_selector(self, expr, default_type):
        """
        Compiles a single selector string to ``(selector_type,
        selector_object, expression_string, attributes)`` where the
        selector_type is a string (``"elements"``, ``"children"``,
        etc), selector_object is a callable that returns elements,
        expression_string is the original expression, passed in, and
        ``attributes`` is a list of attributes in the case of
        ``attributes(attr1, attr2):``
        """
        type, attributes, rest_expr = self.parse_prefix(expr, default_type=default_type)
        if not self.types_compatible(type, self.major_type):
            raise DeliveranceSyntaxError(
                "Expression %s in selector %r uses the type %r, but this is not "
                "compatible with the type %r already declared earlier in the selector"
                % (expr, self, type, self.major_type))
        if rest_expr.startswith('/'):
            selector = XPath(rest_expr)
        else:
            try:
                selector = CSSSelector(rest_expr)
            except AssertionError, e:
                raise DeliveranceSyntaxError('Bad CSS selector: "%s" (%s)' % (expr, e))
        return (type, selector, expr, attributes)

    def __call__(self, doc):
        """
        Match this selector against the doc.  Returns (type, elements,
        attributes), where type is one of elements, children, tag,
        attributes.  attributes is the list of attributes, if that was
        given.
        """
        for sel_type, selector, sel_expr, sel_attributes in self.selectors:
            result = selector(doc)
            if result:
                type = sel_type or self.major_type
                attributes = sel_attributes or self.attributes
                return (type, result, attributes)
        return (self.major_type, [], self.attributes)
    
    def selector_types(self):
        """
        Returns a set of all types used in this expression (usually a
        single-item set, but some selectors can use multiple types).
        """
        return set([sel_type
                    for sel_type, selector, sel_expr, sel_attributes in self.selectors])
    
    def __unicode__(self):
        parts = []
        for sel_type, dummy_selector, sel_expr, sel_attributes in self.selectors:
            if sel_attributes:
                sel_type = '%s(%s)' % (sel_type, ','.join(sel_attributes))
            parts.append('%s:%s' % (sel_type, sel_expr))
        return ' || '.join(parts)

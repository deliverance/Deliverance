"""
Represents individual rules
"""

from deliverance.exceptions import add_exception_info
from deliverance.util.converters import asbool
from deliverance.selector import Selector
from lxml import etree

## A dictionary mapping element names to their rule classes:
rules = {}

class RuleSyntaxError(Exception):
    """
    Exception raised when a rule itself is invalid
    """

class SelectionError(Exception):
    """
    Exception raised when a selection somehow isn't right (e.g.,
    returns no elements when it should return an element).
    """

class AbortTheme(Exception):
    """
    Raised when something aborts via something like nocontent="abort"
    """

CONTENT_ATTRIB = 'x-a-marker-attribute-for-deliverance'

def parse_rule(el, source_location):
    if el.tag not in rules:
        raise RuleSyntaxError(
            "There is no rule with the name %s"
            % el.tag)
    Class = rules[el.tag]
    instance = Class.from_xml(el, source_location)
    return instance

class AbstractRule(object):

    _no_allowed = (None, 'ignore', 'abort', 'warn')
    _many_allowed = _no_allowed + ('last', 'first', 'ignore:first', 'ignore:last',
                                   'warn:first', 'warn:last')

    def convert_error(self, name, value):
        if value == '':
            value = None
        if value:
            value = value.lower()
        bad_options = None
        if name in ('manytheme', 'manycontent'):
            if value not in self._many_allowed:
                bad_options = self._many_allowed
        else:
            if value not in self._no_allowed:
                vad_options = self._no_allowed
        if bad_options:
            raise RuleSyntaxError(
                'The attribute %s="%s" should have a value of one of: %s'
                % (name, value, ', '.join(v for v in bad_options if v)))
        if value and ':' in value:
            value = tuple(value.split(':', 1))
        elif value == 'first':
            value = ('ignore', 'first')
        elif value == 'last':
            value = ('ignore', 'last')
        if name in ('manytheme', 'manycontent'):
            if value == 'ignore':
                value = ('ignore', 'first')
            elif value == 'warn' or not value:
                value = ('warn', 'first')
            elif value == 'abort':
                value = ('abort', None)
        elif not value:
            value = ('warn', None)
        return value

    def format_error(self, attr, value):
        if attr in ('manytheme', 'manycontent'):
            handler, pos = value
            if pos == 'last':
                text = '%s:%s' % (handler, pos)
            else:
                text = handler
        else:
            text = value[0]
            if text == 'warn':
                return None
        return '%s="%s"' % (attr, html_quote(text))

    def if_content_matches(self, content_doc, log):
        """
        Returns true if the if-content selector matches something,
        i.e., if this rule should be executed.
        """
        if self.if_content is None:
            # No if-content means always run
            return True
        sel_type, els, attributes = self.select_elements(self.if_content, content_doc, theme=False)
        matched = bool(els)
        if sel_type == 'elements':
            # els is fine then
            pass
        elif sel_type == 'children':
            matched = False
            for el in els:
                if el.text or len(el):
                    matched = True
                    break
        elif sel_type == 'attributes':
            matched = False
            for el in els:
                if attributes:
                    for attr in attributes:
                        if attr in el.attrib:
                            matched = True
                            break
                    if matched:
                        break
                elif el.attrib:
                    matched = True
                    break
        else:
            ## FIXME: need to make sure 'tag' can't get in here:
            assert 0
        if ((not matched and not self.if_content.inverted)
            or (matched and self.if_content.inverted)):
            log.info(self, 'skipping rule because if-content="%s" does not match', self.if_content)
            if log.describe:
                log.describe('skipping rule %s because if-content="%s" does not match anything'
                             % (self, self.if_content))
            return False
        return True

    name = None
    move_supported = True

    def describe_self(self):
        parts = ['<%s' % self.name]
        if getattr(self, 'content', None):
            parts.append('content="%s"' % html_quote(self.content))
        if getattr(self, 'content_href', None):
            parts.append('href="%s"' % html_quote(self.content_href))
        if self.move_supported and not getattr(self, 'move', False):
            parts.append('move="1"')
        for attr in 'nocontent', 'manycontent':
            value = getattr(self, 'nocontent', ('warn', None))
            if value != ('warn', None):
                parts.append(self.format_error(attr, value))
        if getattr(self, 'theme', None):
            parts.append('theme="%s"' % html_quote(self.theme))
        for attr in 'notheme', 'manytheme':
            value = getattr(self, 'nocontent', ('warn', None))
            if value != ('warn', None):
                parts.append(self.format_error(attr, value))
        ## FIXME: add source_location
        return ' '.join(parts) + ' />'

    def describe_content_elements(self, els, children=False):
        text = ', '.join(el.tag for el in els)
        if children:
            return 'children of %s' % text
        else:
            return text

    def describe_theme_element(self, el):
        return el.tag

    @classmethod
    def compile_selector(cls, tag, attr, source_location):
        value = tag.get(attr)
        if value is None:
            return None
        return Selector.parse(value)
    
    def prepare_content_children(self, els):
        """
        Takes a list of elements and prepares their children as a list and text,
        so that you can do::

          text, els = preparent_content_children(self, els)
          add_text(theme_el, text)
          theme_el.extend(els)

        This is generally for use in content="children:..." rules.
        """
        for i in range(1, len(els)):
            if els[i].text:
                append_to = els[i-1]
                if len(append_to):
                    add_tail(append_to[-1], els[i].text)
                else:
                    add_tail(append_to, els[i].text)
        result = []
        for el in els:
            result.extend(el)
        return els[0].text, result

    def select_elements(self, selector, doc, theme):
        """
        Selects the elements from the document.  `theme` is a boolean,
        true if the document is the theme (in which case elements
        originating in the content are not selectable).
        """
        type, elements, attributes = selector(doc)
        if theme:
            bad_els = []
            for el in elements:
                if is_content_element(el):
                    bad_els.append(el)
            for el in bad_els:
                elements.remove(el)
        return type, elements, attributes

class TransformRule(AbstractRule):
    """
    Abstract class for the rules that move from the content to the theme (replace, append, prepend)
    """

    def __init__(self, source_location, content, theme, if_content=None, content_href=None,
                 move=True, nocontent=None, notheme=None, manytheme=None, manycontent=None):
        self.source_location = source_location
        assert content is not None
        self.content = content
        assert theme is not None
        self.theme = theme
        for content_type in self.content.selector_types():
            for theme_type in self.theme.selector_types():
                if (theme_type, content_type) not in self._compatible_types:
                    raise RuleSyntaxError(
                        'Selector type %s (from content="%s") and type %s (from theme="%s") are not compatible'
                        % (content_type, self.content, theme_type, self.theme))
        self.if_content = if_content
        self.content_href = content_href
        self.move = move
        self.nocontent = self.convert_error('nocontent', nocontent)
        self.notheme = self.convert_error('notheme', notheme)
        self.manytheme = self.convert_error('manytheme', manytheme)
        self.manycontent = self.convert_error('manycontent', manycontent)

    @classmethod
    def from_xml(cls, tag, source_location):
        content = cls.compile_selector(tag, 'content', source_location)
        theme = cls.compile_selector(tag, 'theme', source_location)
        if_content = cls.compile_selector(tag, 'if_content', source_location)
        content_href = tag.get('href')
        move = asbool(tag.get('move', '1'))
        return cls(source_location, content, theme, if_content=if_content,
                   content_href=content_href, move=move,
                   nocontent=tag.get('nocontent'),
                   notheme=tag.get('notheme'),
                   manytheme=tag.get('manytheme'),
                   manycontent=tag.get('manycontent'))

    def apply(self, content_doc, theme_doc, resource_fetcher, log):
        describe = log.describe
        if self.content_href:
            content_doc = resource_fetcher(self.content_href)
        if not self.if_content_matches(content_doc, log):
            return
        content_type, content_els, content_attributes = self.select_elements(self.content, content_doc, theme=False)
        if not content_els:
            if self.nocontent == 'abort':
                log.debug(self, 'aborting theme because no content matches rule content="%s"', self.content)
                raise AbortTheme('No content matches content="%s"' % self.content)
            elif self.nocontent == 'ignore':
                log_meth = log.debug
            else:
                log_meth = log.warn
            log_meth(self, 'skipping rule because no content matches rule content="%s"', self.content)
            if describe:
                describe(
                    'skipping rule %s because content="%s" does not match anything'
                    % (self.describe_self(), html_quote(self.content)))
            return
        theme_type, theme_els, theme_attributes = self.select_elements(self.theme, theme_doc, theme=True)
        attributes = self.join_attributes(content_attributes, theme_attributes)
        if not theme_els:
            if self.notheme == 'abort':
                raise AbortTheme('No theme element matches theme="%s"' % self.theme)
            elif self.notheme == 'ignore':
                log_meth = log.debug
            else:
                log_meth = log.warn
            log_meth(self, 'skipping rule because no theme element matches rule theme="%s"', self.theme)
            if describe:
                describe('skipping rule %s because theme="%s" does not match anything'
                         % (self.describe_self(), html_quote(self.content)))
            return
        if len(theme_els) > 1:
            if self.manytheme[0] == 'warn':
                log.warn(self, '%s elements match theme="%s", using the %s match',
                         len(theme_els), self.theme, self.manytheme[1])
                pass
            elif self.manytheme[0] == 'abort':
                raise AbortTheme('Many elements match theme="%s"' % self.theme)
            if self.manytheme[1] == 'first':
                theme_els = [theme_els[0]]
            else:
                theme_els = [theme_els[-1]]
        theme_el = theme_els[0]
        if not self.move and theme_type in ('children', 'elements'):
            self.log.debug(self, 'content elements are being copied into theme (not moved)')
            content_els = copy.deepcopy(content_els)
        mark_content_els(content_els)
        self.apply_transformation(content_type, content_els, attributes, theme_type, theme_el, log)

    def join_attributes(self, attr1, attr2):
        if not attr1 and not attr2:
            return None
        if attr1 and not attr2:
            return attr1
        if not attr1 and attr2:
            return attr2
        ## FIXME: is a join really the right method?
        attr = set(attr1)
        attr |= attr2
        return list(attr)

class Replace(TransformRule):

    _compatible_types = [
        ('children', 'elements'),
        ('children', 'children'),
        ('elements', 'elements'),
        ('elements', 'children'),
        ('attributes', 'attributes'),
        ('tag', 'tag'),
        ]

    def apply_transformation(self, content_type, content_els, attributes, theme_type, theme_el, log):
        describe = log.describe
        if theme_type == 'children':
            existing_children = len(theme_el) or theme_el.text
            theme_el[:] = []
            theme_el.text = ''
            if content_type == 'elements':
                if self.move:
                    # If we are working with copies, then the tails don't/shouldn't be moved
                    for el in reversed(content_els):
                        move_tail_upward(el)
                else:
                    # If we are working with copies, then we can just throw away the tails
                    for el in content_els:
                        el.tail = None
                theme_el.extend(content_els)
                if describe:
                    if existing_children:
                        extra = ' and removed its children'
                    else:
                        extra = ''
                    describe(
                        "Rule %s moved elements %s into element %s%s"
                        % (self.describe_self(), self.describe_content_elements(content_els), self.describe_theme_element(theme_el), extra))
            elif content_type == 'children':
                text, els = self.prepare_content_children(content_els)
                add_text(theme_el, text)
                theme_el.extend(els)
                if describe:
                    if existing_children:
                        extra = ' and removed its children'
                    else:
                        extra = ''
                    describe(
                        "Rule %s moved the children of elements %s into element %s%s"
                        % (self.describe_self(), self.describe_content_elements(content_els, children=True),
                           self.describe_theme_element(theme_el), extra))
                if self.move:
                    # Since we moved just the children of the content elements, we still need to remove the parent
                    # elements.
                    for el in content_els:
                        el.getparent().remove(el)
            else:
                assert 0
            
        if theme_type == 'elements':
            move_tail_upwards(theme_el)
            parent = theme_el.getparent()
            pos = parent.index(theme_el)
            if content_type == 'elements':
                if self.move:
                    for el in reversed(content_els):
                        move_tail_upwards(el)
                else:
                    for el in content_els:
                        el.tail = None
                parent[pos:pos+1] = content_els
            elif content_type == 'children':
                text, els = self.prepare_content_children(content_els)
                if pos == 0:
                    add_text(parent, text)
                else:
                    add_tail(parent[pos-1], text)
                parent[pos:pos+1] = els
                if self.move:
                    for el in content_els:
                        el.getparent().remove(el)
            else:
                assert 0

        if theme_type == 'attributes':
            ## FIXME: handle named attributes, e.g., attributes(class):
            assert content_type == 'attributes'
            if len(content_els) > 1:
                if self.manycontent[0] == 'abort':
                    log.debug(self, 'aborting because %s elements in the content match content="%s"',
                              len(content_els), self.content)
                    raise AbortTheme()
                else:
                    if self.manycontent[0] == 'warn':
                        log_meth = log.warn
                    else:
                        log_meth = log.debug
                    log_meth(self, '%s elements match content="%s" (but only one expected), using the %s match',
                             len(content_els, self.content, self.manycontent[1]))
                    if self.manycontent[1] == 'first':
                        content_els = [content_els[0]]
                    else:
                        content_els = [content_els[-1]]
            theme_el.attrib.clear()
            if attributes:
                c_attrib = content_els[0].attrib
                for name in attributes:
                    if name in c_attrib:
                        theme_el.set(name, c_attrib[name])
                if self.move:
                    for name in attributes:
                        if name in c_attrib:
                            del c_attrib[name]
            else:
                theme_el.attrib.update(content_els[0].attrib)
                if self.move:
                    content_els[0].attrib.clear()

        if theme_type == 'tag':
            assert content_type == 'tag'
            theme_el.tag = content_els[0].tag
            theme_el.attrib.clear()
            theme_el.attrib.update(content_els[0].attrib)
            # "move" in this case doesn't mean anything

rules['replace'] = Replace

class Append(TransformRule):

    _append = True

    _compatible_types = [
        ('children', 'elements'),
        ('children', 'children'),
        ('elements', 'elements'),
        ('elements', 'children'),
        ('attributes', 'attributes'),
        # Removing 'tag'
        ]

    def apply_transformation(self, content_type, content_els, attributes, theme_type, theme_el, log):
        describe = log.describe
        if theme_type == 'children':
            if content_type == 'elements':
                if self.move:
                    for el in reversed(content_els):
                        move_tail_upwards(el)
                else:
                    for el in content_els:
                        el.tail = None
                if self._append:
                    theme_el.extend(content_els)
                else:
                    add_tail(content_els[-1], theme_el.text)
                    theme_el.text = None
                    theme_el[:0] = content_els
            elif content_type == 'children':
                text, els = self.preparent_content_children(content_els)
                if self._append:
                    if len(theme_el):
                        add_tail(theme_el[-1], text)
                    else:
                        add_text(theme_el, text)
                    theme_el.extend(els)
                else:
                    add_tail(els[-1], theme_el.text)
                    theme_el.text = text
                    theme_el[:0] = els
            else:
                assert 0

        if theme_type == 'elements':
            parent = theme_el.getparent()
            pos = parent.index(theme_el)
            if content_type == 'elements':
                if self.move:
                    for el in reversed(content_els):
                        move_tail_upwards(el)
                else:
                    for el in content_els:
                        el.tail = None
                if self._append:
                    parent[pos+1:pos+1] = content_els
                else:
                    parent[pos:pos] = content_els
            elif content_type == 'children':
                text, els = self.prepare_content_children(content_els)
                if self._append:
                    add_tail(theme_el, text)
                    parent[pos+1:pos+1] = content_els
                else:
                    if pos == 0:
                        add_text(parent, text)
                    else:
                        add_tail(parent[pos-1], text)
                    parent[pos:pos] = content_els

        if theme_type == 'attributes':
            ## FIXME: handle named attributes
            assert content_type == 'attributes'
            if len(content_els) > 1:
                if self.manycontent[0] == 'abort':
                    log.debug(self, 'aborting because %s elements in the content match content="%s"',
                              len(content_els), self.content)
                    raise AbortTheme()
                else:
                    if self.manycontent[0] == 'warn':
                        log_meth = log.warn
                    else:
                        log_meth = log.debug
                    log_meth(self, '%s elements match content="%s" (but only one expected), using the %s match',
                             len(content_els, self.content, self.manycontent[1]))
                    if self.manycontent[1] == 'first':
                        content_els = [content_els[0]]
                    else:
                        content_els = [content_els[-1]]
            content_attrib = content_els[0].attrib
            theme_attrib = theme_el.attrib
            if self._append:
                if attributes:
                    for name in attributes:
                        if name in content_attrib:
                            theme_attrib.setdefault(name, content_attrib[name])
                else:
                    for key, value in content_attrib.items():
                        theme_attrib.setdefault(key, value)
            else:
                if attributes:
                    for name in attributes:
                        if name in content_attrib:
                            theme_attrib.set(name, content_attrib[name])
                else:
                    theme_attrib.update(content_attrib)
            if self.move:
                if attributes:
                    for name in attributes:
                        if name in content_attrib:
                            del content_attrib[name]
                else:
                    content_attrib.clear()

rules['append'] = Append

class Prepend(Append):
    _append = False

rules['prepend'] = Prepend

class Drop(AbstractRule):
    
    def __init__(self, source_location, content, theme, if_content=None,
                 nocontent=None, notheme=None):
        self.source_location = source_location
        ## FIXME: proper error:
        assert content is not None or theme is not None
        self.content = content
        assert theme is not None
        self.theme = theme
        self.if_content = if_content
        self.nocontent = self.convert_error('nocontent', nocontent)
        self.notheme = self.convert_error('notheme', notheme)

    def apply(self, content_doc, theme_doc, resource_fetcher, log):
        describe = log.describe
        if not self.if_content_matches(content_doc, log):
            return
        for doc, selector, error, name in [(theme_doc, self.theme, self.notheme, 'theme'), (content_doc, self.content, self.nocontent, 'content')]:
            if selector is None:
                continue
            sel_type, els, attributes = self.select_elements(selector, doc, name=='theme')
            if not els:
                if error == 'abort':
                    log.debug(self, 'aborting %s because no %s element matches rule %s="%s"', name, name, name, selector)
                    raise AbortTheme('No %s matches %s="%s"' % (name, name, selector))
                elif error == 'ignore':
                    log_meth = log.debug
                else:
                    log_meth = log.warn
                log_meth(self, 'skipping rule because no %s matches rule %s="%s"', name, name, selector)
                return
            if sel_type == 'elements':
                for el in els:
                    move_tail_upwards(el)
                    el.getparent().remove(el)
            elif sel_type == 'children':
                el[:] = []
                el.text = ''
            elif sel_type == 'attributes':
                attrib = el.attrib
                if attributes:
                    for name in attributes:
                        if name in attrib:
                            del attrib[name]
                else:
                    attrib.clear()
            elif sel_type == 'tag':
                children = list(el)
                if children:
                    add_tail(children[-1], el.tail)
                else:
                    add_text(el, el.tail)
                parent = el.getparent()
                pos = parent.index(el)
                if pos == 0:
                    add_text(parent, el.text)
                else:
                    add_tail(parent[pos-1], el.text)
                parent[pos:pos+1] = children
            else:
                assert 0

    @classmethod
    def from_xml(cls, tag, source_location):
        content = cls.compile_selector(tag, 'content', source_location)
        theme = cls.compile_selector(tag, 'theme', source_location)
        if_content = cls.compile_selector(tag, 'if_content', source_location)
        return cls(source_location, content, theme, if_content=if_content,
                   nocontent=tag.get('nocontent'),
                   notheme=tag.get('notheme'))

rules['drop'] = Drop
            
## Element utilities ##

def add_text(el, text):
    """
    Add the given text to the end of the el's text
    """
    if not text:
        return
    if el.text:
        el.text += text
    else:
        # Note, el.text can be None (so we can't always add)
        el.text = text

def add_tail(el, tail):
    """
    Add the given tail text to the end of the el's tail
    """
    if not tail:
        return
    if el.tail:
        el.tail += tail
    else:
        # Note, el.tail can be None (so we can't always add)
        el.tail = tail

def move_tail_upwards(el):
    """
    Move the tail of the el into its previous sibling or parent
    """
    dest = el.getprevious()
    if dest is not None:
        add_tail(dest, el.tail)
    else:
        parent = el.getparent()
        add_text(parent, el.tail)

def iter_self_and_ancestors(el):
    yield el
    for item in el.iterancestors():
        yield item

def mark_content_els(els):
    for el in els:
        ## FIXME: maybe put something that is trackable to the rule that moved the element
        el.set(CONTENT_ATTRIB, '1')

def is_content_element(el):
    ## FIXME: should this check children too?
    for p in iter_self_and_ancestors(el):
        if p.get(CONTENT_ATTRIB):
            return True
    return False

def remove_content_attribs(doc):
    for p in doc.getiterator():
        if p.get(CONTENT_ATTRIB, None) is not None:
            del p.attrib[CONTENT_ATTRIB]

from cgi import escape as cgi_escape
def html_quote(s):
    s = unicode(s)
    return cgi_escape(s, True)

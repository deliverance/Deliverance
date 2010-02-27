"""
Represents individual actions (``<append>`` etc) and the RuleSet that
puts them together
"""

import copy
import urlparse
from lxml import etree
from lxml.html import document_fromstring, tostring
from urllib import quote as url_quote
from tempita import html
from deliverance.exceptions import DeliveranceSyntaxError, AbortTheme
from deliverance.util.converters import asbool, html_quote
from deliverance.selector import Selector
from deliverance.pagematch import AbstractMatch
from deliverance.themeref import Theme
from deliverance.util.cdata import escape_cdata, unescape_cdata
from deliverance.util.charset import fix_meta_charset_position

CONTENT_ATTRIB = 'x-a-marker-attribute-for-deliverance'

class Rule(object):
    """
    This represents everything in a <rule></rule> section.
    """

    def __init__(self, classes, actions, theme, match, suppress_standard, 
                 source_location):
        self.classes = classes
        self._actions = actions
        self.theme = theme
        self.match = match
        self.suppress_standard = suppress_standard
        self.source_location = source_location

    @classmethod
    def parse_xml(cls, el, source_location):
        """
        Creates a Rule object from a parsed XML <rule> element.
        """
        assert el.tag == 'rule'
        classes = el.get('class', '').split()
        if not classes:
            classes = ['default']
        theme = None
        actions = []
        suppress_standard = asbool(el.get('suppress-standard'))
        for child in el.iterchildren():
            if child.tag == 'theme':
                ## FIXME: error if more than one theme
                theme = Theme.parse_xml(child, source_location)
                continue
            if child.tag is etree.Comment:
                continue
            action = parse_action(child, source_location)
            actions.append(action)
        match = None
        inst = cls(classes, actions, theme, match, suppress_standard, source_location)
        for attr in RuleMatch.match_attrs:
            if el.get(attr):
                inst.match = RuleMatch.parse_xml(inst, el, source_location)
                ## FIXME: would last="1" be a good alternative to suppress-standard?
                break
        return inst

    def apply(self, content_doc, theme_doc, resource_fetcher, log):
        """
        Applies all the actions in this rule to the theme_doc

        Note that this leaves behind attributes to mark elements that
        originated in the content.  You should call
        :func:`remove_content_attribs` after applying all rules.
        """
        for action in self._actions:
            action.apply(content_doc, theme_doc, resource_fetcher, log)
        return theme_doc

    def clientside_actions(self, content_doc, log):
        actions = []
        for action in self._actions:
            actions.extend(action.clientside_actions(content_doc, log))
        return actions

class RuleMatch(AbstractMatch):
    """
    Represents match rules in the <rule> element
    """

    element_name = 'rule'

    @classmethod
    def parse_xml(cls, rule, el, source_location):
        """
        Parse this match from the attributes in the given element.
        """
        inst = cls(**cls.parse_match_xml(el, source_location))
        inst.rule = rule
        return inst

    def debug_description(self):
        """Used by AbstractMatch for logging"""
        return '<rule>'

    def log_context(self):
        """Used by AbstractMatch for logging"""
        return self.rule

## A dictionary mapping element names to their rule classes:
_actions = {}

def parse_action(el, source_location):
    """
    Parses an element into an action object.
    """
    if el.tag not in _actions:
        raise DeliveranceSyntaxError(
            "There is no rule with the name %s"
            % el.tag)
    Class = _actions[el.tag]
    instance = Class.from_xml(el, source_location)
    return instance

def clientside_action(action_name, content_selector, theme_selector):
    """Create one Action instance based on a clientside web subrequest"""
    ActionClass = _actions[action_name]
    return ActionClass(
        source_location='web', content=Selector.parse(content_selector),
        theme=Selector.parse(theme_selector))

class AbstractAction(object):
    """Abstract superclass for Actions (replace, etc)"""

    # These values are allowed for nocontent and notheme attributes:
    _no_allowed = (None, 'ignore', 'abort', 'warn')
    # These values are allowed for manycontent and manytheme attributes:
    _many_allowed = _no_allowed + ('last', 'first', 'ignore:first', 'ignore:last',
                                   'warn:first', 'warn:last')

    # Subclasses should set these up in instantiation:
    if_content = None
    source_location = None
    content = None
    content_href = None
    theme = None

    def convert_error(self, name, value):
        """
        Taking a ``name="value"`` attribute for an error type
        (nocontent, manycontent, etc) this returns ``(error_handler,
        position)`` (where ``position`` is None for notheme/nocontent).

        This applies the default value of "warn" and the default
        position of "first".
        """
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
                bad_options = self._no_allowed
        if bad_options:
            raise DeliveranceSyntaxError(
                'The attribute %s="%s" should have a value of one of: %s'
                % (name, value, ', '.join(v for v in bad_options if v)))
        if not value:
            value = 'warn'
        if name in ('nocontent', 'notheme'):
            return value
        # Must be manytheme/manycontent, which is (error_handler, fallback)
        if value and ':' in value:
            value = tuple(value.split(':', 1))
        elif value == 'first':
            value = ('ignore', 'first')
        elif value == 'last':
            value = ('ignore', 'last')
        elif value == 'ignore':
            value = ('ignore', 'first')
        elif value == 'warn':
            value = ('warn', 'first')
        elif value == 'abort':
            value = ('abort', None)
        else:
            assert 0, "Unexpected value: %r" % repr(value)
        return value

    def format_error(self, attr, value):
        """
        Takes the result of :meth:`convert_error` and serializes it
        back into ``attribute="value"``
        """
        if attr in ('manytheme', 'manycontent'):
            assert isinstance(value, tuple), (
                "Unexpected value: %r (for attribute %s)" % (
                    value, attr))
            if value == ('warn', 'first'):
                return None
            handler, pos = value
            if pos == 'last':
                text = '%s:%s' % (handler, pos)
            else:
                text = handler
        else:
            text = value
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
        sel_type, els, attributes = self.select_elements(
            self.if_content, content_doc, theme=False)
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
            log.info(self, 'skipping rule because if-content="%s" does not match', 
                     self.if_content)
            return False
        return True

    # Set to the tag name in subclasses (append, prepend, etc):
    name = None
    # Set to true in subclasses if the move attribute means something:
    move_supported = True

    def __unicode__(self):
        return unicode(self.log_description(log=None))

    def __str__(self):
        return unicode(self).encode('utf8')

    @classmethod
    def compile_selector(cls, el, attr, source_location, invertable=False):
        """
        Compiles a single selector taken from the given attribute of
        an element.
        """
        inverted = False
        value = el.get(attr)
        if value is None:
            return None
        inverted = False
        if invertable and value.strip().startswith('not:'):
            inverted = True
            value = value.strip()[4:]
        result = Selector.parse(value)
        if invertable:
            result.inverted = inverted
        return result
    
    def prepare_content_children(self, els):
        """
        Takes a list of elements and prepares their children as a list and text,
        so that you can do::

          text, els = prepare_content_children(self, els)
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

    def log_description(self, log=None):
        """
        A text description of this rule, for use in log messages and errors
        """
        def linked_item(url, body, source=None, line=None, selector=None):
            """Creates a link, if we have a log context"""
            body = html_quote(body)
            if log is None or url is None:
                return body
            link = log.link_to(url, source=source, line=line, selector=selector)
            return '<a href="%s" target="_blank">%s</a>' % (html_quote(link), body)
        if log:
            request_url = log.request.url
        else:
            request_url = None
        parts = ['&lt;%s' % linked_item(self.source_location, self.name, source=True)]
        if getattr(self, 'content', None):
            body = 'content="%s"' % html_quote(self.content)
            if getattr(self, 'content_href', None):
                if request_url:
                    content_url = urlparse.urljoin(request_url, self.content_href)
                else:
                    content_url = self.content_href
            else:
                content_url = request_url
            parts.append(linked_item(content_url, body, selector=self.content))
        if getattr(self, 'content_href', None):
            dest = self.content_href
            if request_url:
                dest = urlparse.urljoin(request_url, dest)
            body = 'href="%s"' % html_quote(self.content_href)
            parts.append(linked_item(dest, body, source=True))
        if self.move_supported and not getattr(self, 'move', False):
            parts.append('move="0"')
        v = getattr(self, 'nocontent', 'warn')
        if v != 'warn':
            parts.append(self.format_error('nocontent', v))
        v = getattr(self, 'manycontent', ('warn', None))
        if v != ('warn', 'first'):
            parts.append(self.format_error('manycontent', v))
        if getattr(self, 'theme', None):
            body = 'theme="%s"' % html_quote(self.theme)
            theme_url = getattr(log, 'theme_url', None)
            parts.append(linked_item(theme_url, body, selector=self.theme))
        v = getattr(self, 'notheme', 'warn')
        if v != 'warn':
            parts.append(self.format_error('notheme', v))
        v = getattr(self, 'manytheme', ('warn', None))
        if v != ('warn', 'first'):
            parts.append(self.format_error('manytheme', v))
        ## FIXME: add source_location
        return html(' '.join(parts) + ' /&gt;')
        
    def format_tags(self, elements, include_name=True):
        """Formats the tags for display in a log message.

        If `include_name` is true then "element" or "elements" is put
        before the elements.
        """
        if not elements:
            if include_name:
                return 'no elements'
            else:
                return '(none)'
        text = ', '.join('<%s>' % el.tag for el in elements)
        if include_name:
            if len(elements) > 1:
                return 'elements %s' % text
            else:
                return 'element %s' % text
        else:
            return text

    def format_tag(self, tag, include_name=False):
        """
        Formats a single tag.
        """
        return self.format_tags([tag], include_name=include_name)

    def format_attribute_names(self, attributes, include_name=True):
        """
        Formats attribute names for display in a log message.

        If `include_name` is true, then "attribute" or "attributes" is
        put before the attribute names.
        """
        if not attributes:
            if include_name:
                return 'no attributes'
            else:
                return '(none)'
        text = ', '.join(attributes)
        if include_name:
            if len(attributes) > 1:
                return 'attributes %s' % text
            else:
                return 'attribute %s' % text
        else:
            return text
        
class TransformAction(AbstractAction):
    """Abstract class for the rules that move from the content to the
    theme (replace, append, prepend)"""

    # Subclasses must set this:
    _compatible_types = []

    def __init__(self, source_location, content, theme, if_content=None, 
                 content_href=None, move=True, nocontent=None, notheme=None, 
                 manytheme=None, manycontent=None):
        self.source_location = source_location
        assert content is not None
        self.content = content
        assert theme is not None or source_location == 'web'
        self.theme = theme
        if theme is not None:
            for content_type in self.content.selector_types():
                for theme_type in self.theme.selector_types():
                    if (theme_type, content_type) not in self._compatible_types:
                        raise DeliveranceSyntaxError(
                            'Selector type %s (from content="%s") and type %s '
                            '(from theme="%s") are not compatible'
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
        """
        Creates an instance of this object from the given parsed XML element
        """
        content = cls.compile_selector(tag, 'content', source_location)
        theme = cls.compile_selector(tag, 'theme', source_location)
        if_content = cls.compile_selector(tag, 'if-content', source_location, invertable=True)
        content_href = tag.get('href')
        move = asbool(tag.get('move', '1'))
        return cls(source_location, content, theme, if_content=if_content,
                   content_href=content_href, move=move,
                   nocontent=tag.get('nocontent'),
                   notheme=tag.get('notheme'),
                   manytheme=tag.get('manytheme'),
                   manycontent=tag.get('manycontent'))

    def apply(self, content_doc, theme_doc, resource_fetcher, log):
        """
        Applies this action to the theme_doc.
        """
        if self.content_href:
            ## FIXME: Is this a weird way to resolve the href?
            href = urlparse.urljoin(log.request.url, self.content_href)
            content_resp = resource_fetcher(href)
            log.debug(
                self, 'Fetching resource from href="%s": %s',
                href, content_resp.status)
            if content_resp.status_int != 200:
                log.warn(
                    self, 'Resource %s returned the status %s; skipping rule',
                    href, content_resp.status)
                return
            body = content_resp.body
            body = escape_cdata(body)
            body = fix_meta_charset_position(body)
            content_doc = document_fromstring(
                body, base_url=self.content_href)
        if not self.if_content_matches(content_doc, log):
            return
        content_type, content_els, content_attributes = self.select_elements(
            self.content, content_doc, theme=False)
        if not content_els:
            if self.nocontent == 'abort':
                log.debug(
                    self, 'aborting theming because no content matches rule content="%s"',
                    self.content)
                raise AbortTheme('No content matches content="%s"' % self.content)
            elif self.nocontent == 'ignore':
                log_meth = log.debug
            else:
                log_meth = log.warn
            log_meth(
                self, 'skipping rule because no content matches rule content="%s"', 
                self.content)
            return
        theme_type, theme_els, theme_attributes = self.select_elements(
            self.theme, theme_doc, theme=True)
        attributes = self.join_attributes(content_attributes, theme_attributes)
        if not theme_els:
            if self.notheme == 'abort':
                log.debug(
                    self, 
                    'aborting theming because no theme elements match rule theme="%s"', 
                    self.theme)
                raise AbortTheme('No theme element matches theme="%s"' % self.theme)
            elif self.notheme == 'ignore':
                log_meth = log.debug
            else:
                log_meth = log.warn
            log_meth(
                self, 'skipping rule because no theme element matches rule theme="%s"', 
                self.theme)
            return
        if len(theme_els) > 1:
            if self.manytheme[0] == 'abort':
                log.debug(
                    self, 'aborting theming because %i elements (%s) match theme="%s"',
                    len(theme_els), self.format_tags(theme_els, include_name=False), 
                    self.theme)
                raise AbortTheme('Many elements match theme="%s"' % self.theme)
            elif self.manytheme[0] == 'warn':
                log_meth = log.warn
            else:
                log_meth = log.debug
            if self.manytheme[1] == 'first':
                theme_el = theme_els[0]
            else:
                theme_el = theme_els[-1]
            log_meth(
                self, '%s elements match theme="%s", using the %s match',
                len(theme_els), self.theme, self.manytheme[1])
        else:
            theme_el = theme_els[0]
        if not self.move and theme_type in ('children', 'elements'):
            content_els = copy.deepcopy(content_els)
        mark_content_els(content_els)
        self.apply_transformation(content_type, content_els, attributes, 
                                  theme_type, theme_el, log)

    def clientside_actions(self, content_doc, log):
        if self.content_href:
            href = urlparse.urljoin(log.request.url, self.content_href)
            url = '%s/.deliverance/subreq?url=%s&action=%s&content=%s&theme=%s' % (
                log.request.application_url,
                url_quote(href),
                url_quote(self.name),
                url_quote(str(self.content)),
                url_quote(str(self.theme)))
            return [{'mode': 'include',
                     'callback': url}]
        if not self.if_content_matches(content_doc, log):
            return []
        content_type, content_els, content_attributes = self.select_elements(
            self.content, content_doc, theme=False)
        if not content_els:
            if self.nocontent == 'abort':
                ## FIXME: uh oh
                raise AbortTheme('No content matches content="%s"' % self.content)
            else:
                ## FIXME: log
                return []
        theme_type, theme_selector = str(self.theme).split(':', 1)
        data = {'type': self.name,
                'mode': theme_type,
                'selector': theme_selector}
        if content_type == 'attributes' or content_type == 'tag':
            data['attributes'] = dict(content_els[0].attrib)
        if content_type == 'tag':
            data['tag'] = content_els[0].tag
        elif content_type == 'children':
            text = []
            for el in content_els:
                text.append(el.text)
                for child in el:
                    text.append(tostring(child))
            data['content'] = ''.join(text)
        elif content_type == 'elements':
            text = []
            for el in content_els:
                ## FIXME: sloppy :(
                el.tail = None
                text.append(tostring(el))
            data['content'] = ''.join(text)
        return [data]

    def join_attributes(self, attr1, attr2):
        """
        Joins the sets of attribute names in attr1 and attr2, where either might be None
        """
        if not attr1 and not attr2:
            return None
        if attr1 and not attr2:
            return attr1
        if not attr1 and attr2:
            return attr2
        ## FIXME: is a join really the right method?
        attr = set(attr1)
        attr |= set(attr2)
        return list(attr)

    def apply_transformation(self, content_type, content_els, attributes, 
                             theme_type, theme_el, log):
        """Subclasses override this to implement the actual transformation
        """
        raise NotImplementedError

class Replace(TransformAction):
    """Implements the <replace> action"""

    # Compatible types of child and theme selector types:
    _compatible_types = [
        ('children', 'elements'),
        ('children', 'children'),
        ('elements', 'elements'),
        ('elements', 'children'),
        ('attributes', 'attributes'),
        ('tag', 'tag'),
        ]

    name = 'replace'
 
    def apply_transformation(self, content_type, content_els, attributes, 
                             theme_type, theme_el, log):
        """Apply the <replace> action"""
        if theme_type == 'children':
            if len(theme_el):
                log_text = 'and removed the chilren and text of the theme element'
            elif theme_el.text:
                log_text = 'and removed the text content of the theme element'
            else:
                log_text = '(the theme was already empty)'
            theme_el[:] = []
            theme_el.text = ''
            if content_type == 'elements':
                if self.move:
                    # If we aren't working with copies then we have to
                    # move the tails up as we remove the elements:
                    for el in reversed(content_els):
                        move_tail_upwards(el)
                    verb = 'Moving'
                else:
                    # If we are working with copies, then we can just
                    # throw away the tails:
                    for el in content_els:
                        el.tail = None
                    verb = 'Copying'
                theme_el.extend(content_els)
                log.debug(
                    self, '%s %s from content into theme element %s %s',
                    verb, self.format_tags(content_els), self.format_tag(theme_el), 
                    log_text)
            elif content_type == 'children':
                text, els = self.prepare_content_children(content_els)
                add_text(theme_el, text)
                theme_el.extend(els)
                if self.move:
                    # Since we moved just the children of the content
                    # elements, we still need to remove the parent
                    # elements.
                    for el in content_els:
                        el.getparent().remove(el)
                    log.debug(
                        self, 'Moving children of content %s into theme element %s, '
                        'and removing now-empty content elements %s',
                        self.format_tags(content_els), self.format_tag(theme_el), 
                        log_text)
                else:
                    log.debug(
                        self, 'Copying children of content %s into theme element %s %s',
                        self.format_tags(content_els), self.format_tag(theme_el), 
                        log_text)
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
                    verb = 'moved'
                else:
                    for el in content_els:
                        el.tail = None
                    verb = 'copied'
                parent[pos:pos+1] = content_els
                log.debug(
                    self, 'Replaced the theme element %s with the content %s (%s)',
                    self.format_tag(theme_el), self.format_tags(content_els), verb)
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
                    log.debug(
                        self, 'Replaced the theme element %s with the children of the '
                        'content %s, and removed the now-empty content element(s)',
                        self.format_tag(theme_el), self.format_tags(content_els))
                else:
                    log.debug(
                        self, 'Replaced the theme element %s with copies of the '
                        'children of the content %s',
                        self.format_tag(theme_el), self.format_tags(content_els))
            else:
                assert 0

        if theme_type == 'attributes':
            ## FIXME: handle named attributes, e.g., attributes(class):
            assert content_type == 'attributes'
            if len(content_els) > 1:
                if self.manycontent[0] == 'abort':
                    log.debug(
                        self, 'aborting because %i elements in the content (%s) '
                        'match content="%s"',
                        len(content_els), 
                        self.format_tags(content_els, include_name=False), self.content)
                    raise AbortTheme()
                else:
                    if self.manycontent[0] == 'warn':
                        log_meth = log.warn
                    else:
                        log_meth = log.debug
                    log_meth(
                        self, '%s elements match content="%s" (%s) when only one is '
                        'expected, using the %s match',
                        len(content_els), self.content, 
                        self.format_tags(content_els, include_name=False), 
                        self.manycontent[1])
                    if self.manycontent[1] == 'first':
                        content_els = [content_els[0]]
                    else:
                        content_els = [content_els[-1]]
            if theme_el.attrib:
                log_text = ' and cleared all existing theme attributes'
            else:
                log_text = ''
            ## FIXME: should this only clear the named attribute?
            ## (when attributes are named)
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
                    log_text += ' and removed the attributes from the content'
                ## FIXME: only list attributes that were actually found?
                log.debug(
                    self, 'Copied the %s from the content element %s to the '
                    'theme element %s%s',
                    self.format_attribute_names(attributes), 
                    self.format_tag(content_els[0]), self.format_tag(theme_el), log_text)
            else:
                theme_el.attrib.update(dict(content_els[0].attrib))
                if self.move:
                    content_els[0].attrib.clear()
                    log_text += ' and removed all attributes from the content'
                log.debug(
                    self, 'Moved all the attributes from the content element %s to the '
                    'theme element %s%s',
                    self.format_tag(content_els[0]), self.format_tag(theme_el), log_text)

        if theme_type == 'tag':
            ## FIXME: warn about manycontent
            assert content_type == 'tag'
            old_tag = theme_el.tag
            theme_el.tag = content_els[0].tag
            theme_el.attrib.clear()
            theme_el.attrib.update(content_els[0].attrib)
            # "move" in this case doesn't mean anything
            log.debug(
                self, 'Changed the tag name of the theme element <%s> to the '
                'name of the content element: %s',
                old_tag, self.format_tag(content_els[0]))


        

_actions['replace'] = Replace

class Append(TransformAction):
    """Implements the <append> action"""

    name = 'append'

    # This is set to False in Prepend:
    _append = True

    _compatible_types = [
        ('children', 'elements'),
        ('children', 'children'),
        ('elements', 'elements'),
        ('elements', 'children'),
        ('attributes', 'attributes'),
        # Removing 'tag'
        ]

    def apply_transformation(self, content_type, content_els, attributes, 
                             theme_type, theme_el, log):
        """Applies the transformation"""
        if theme_type == 'children':
            if content_type == 'elements':
                if self.move:
                    for el in reversed(content_els):
                        move_tail_upwards(el)
                    verb = 'Moving'
                else:
                    for el in content_els:
                        el.tail = None
                    verb = 'Copying'
                if self._append:
                    theme_el.extend(content_els)
                    pos_text = 'end'
                else:
                    add_tail(content_els[-1], theme_el.text)
                    theme_el.text = None
                    theme_el[:0] = content_els
                    pos_text = 'beginning'
                log.debug(
                    self, '%s content %s to the %s of theme element %s',
                    verb, self.format_tags(content_els), pos_text, 
                    self.format_tag(theme_el))
            elif content_type == 'children':
                text, els = self.prepare_content_children(content_els)
                if self._append:
                    if len(theme_el):
                        add_tail(theme_el[-1], text)
                    else:
                        add_text(theme_el, text)
                    theme_el.extend(els)
                    pos_text = 'end'
                else:
                    if len(els):
                        add_tail(els[-1], theme_el.text)
                        theme_el.text = text
                    else:
                        old_text = theme_el.text
                        theme_el.text = text or ''
                        if old_text:
                            theme_el.text += old_text
                    theme_el[:0] = els
                    pos_text = 'beginning'
                if self.move:
                    for el in reversed(content_els):
                        move_tail_upwards(el)
                        el.getparent().remove(el)
                    verb = 'Moving'
                    log_text = ' and removing the now-empty content element(s)'
                else:
                    verb = 'Copying'
                    log_text = ''
                log.debug(
                    self, '%s the children of content %s to the %s of the '
                    'theme element %s%s',
                    verb, self.format_tags(content_els), pos_text, 
                    self.format_tag(theme_el), log_text)
            else:
                assert 0

        if theme_type == 'elements':
            parent = theme_el.getparent()
            pos = parent.index(theme_el)
            if content_type == 'elements':
                if self.move:
                    for el in reversed(content_els):
                        move_tail_upwards(el)
                    verb = 'Moving'
                else:
                    for el in content_els:
                        el.tail = None
                    verb = 'Copying'
                if self._append:
                    parent[pos+1:pos+1] = content_els
                    pos_text = 'after'
                else:
                    parent[pos:pos] = content_els
                    pos_text = 'before'
                log.debug(
                    self, '%s content %s %s the theme element %s',
                    verb, self.format_tags(content_els), pos_text, 
                    self.format_tag(theme_el))
            elif content_type == 'children':
                text, els = self.prepare_content_children(content_els)
                if self._append:
                    add_tail(theme_el, text)
                    parent[pos+1:pos+1] = content_els
                    pos_text = 'after'
                else:
                    if pos == 0:
                        add_text(parent, text)
                    else:
                        add_tail(parent[pos-1], text)
                    parent[pos:pos] = content_els
                    pos_text = 'before'
                if self.move:
                    for el in reversed(content_els):
                        move_tail_upwards(el)
                        el.getparent().remove(el)
                    verb = 'Moving'
                    log_text = ' and removing the now-empty content element(s)'
                else:
                    verb = 'Copying'
                    log_text = ''
                log.debug(
                    self, '%s the children of content %s %s the theme element %s%s',
                    verb, self.format_tags(content_els), pos_text, 
                    self.format_tag(theme_el), log_text)

        if theme_type == 'attributes':
            ## FIXME: handle named attributes
            assert content_type == 'attributes'
            if len(content_els) > 1:
                if self.manycontent[0] == 'abort':
                    log.debug(
                        self, 'aborting because %i elements in the content (%s) '
                        'match content="%s"',
                        len(content_els), self.format_tags(content_els), self.content)
                    raise AbortTheme()
                else:
                    if self.manycontent[0] == 'warn':
                        log_meth = log.warn
                    else:
                        log_meth = log.debug
                    log_meth(
                        self, '%s elements match content="%s" (%s) but only one '
                        'is expected, using the %s match',
                        len(content_els), self.content, self.format_tags(content_els),
                        self.manycontent[1])
                    if self.manycontent[1] == 'first':
                        content_els = [content_els[0]]
                    else:
                        content_els = [content_els[-1]]
            content_attrib = content_els[0].attrib
            theme_attrib = theme_el.attrib
            if self.move:
                verb = 'Moved'
            else:
                verb = 'Copied'
            if self._append:
                if attributes:
                    avoided_attrs = []
                    copied_attrs = []
                    for name in attributes:
                        if name in content_attrib:
                            if name in theme_attrib:
                                avoided_attrs.append(name)
                            else:
                                theme_attrib[name] = content_attrib[name]
                                copied_attrs.append(name)
                    if avoided_attrs:
                        log.debug(
                            self, '%s %s from the content element %s to the theme '
                            'element %s, and did not copy the %s because they were '
                            'already present in the theme element',
                            verb, self.format_attribute_names(copied_attrs), 
                            self.format_tag(content_els[0]), self.format_tag(theme_el), 
                            self.format_attribute_names(avoided_attrs))
                    else:
                        log.debug(
                            self, '%s %s from the content element %s to the theme '
                            'element %s',
                            verb, self.format_attribute_names(copied_attrs), 
                            self.format_tag(content_els[0]), self.format_tag(theme_el))
                else:
                    avoided_attrs = []
                    copied_attrs = []
                    for key, value in content_attrib.items():
                        if key in theme_attrib:
                            avoided_attrs.append(key)
                        else:
                            copied_attrs.append(key)
                            theme_attrib[key] = value
                    if avoided_attrs:
                        log.debug(
                            self, '%s %s from the content element %s to the theme '
                            'element %s, and did not copy the %s because they were '
                            'already present in the theme element',
                            verb, self.format_attribute_names(copied_attrs), 
                            self.format_tag(content_els[0]), self.format_tag(theme_el), 
                            self.format_attribute_names(avoided_attrs))
                    else:
                        log.debug(
                            self, 
                            '%s %s from the content element %s to the theme element %s',
                            verb, self.format_attribute_names(copied_attrs), 
                            self.format_tag(content_els[0]), self.format_tag(theme_el))
            else:
                if attributes:
                    for name in attributes:
                        if name in content_attrib:
                            theme_attrib.set(name, content_attrib[name])
                    log.debug(
                        self, '%s %s from the content element %s to the theme element %s',
                        verb, self.format_attribute_names(attributes), 
                        self.format_tag(content_els[0]), self.format_tag(theme_el))
                else:
                    theme_attrib.update(content_attrib)
                    log.debug(
                        self, '%s all the attributes from the content element %s '
                        'to the theme element %s',
                        verb, self.format_tag(content_els[0]), self.format_tag(theme_el))
            if self.move:
                if attributes:
                    for name in attributes:
                        if name in content_attrib:
                            del content_attrib[name]
                else:
                    content_attrib.clear()

_actions['append'] = Append

class Prepend(Append):
    """Implements the <prepend> action"""
    name = 'prepend'
    _append = False

_actions['prepend'] = Prepend

class Drop(AbstractAction):
    """Implements the <drop> action"""
    
    name = 'drop'

    def __init__(self, source_location, content, theme, if_content=None,
                 nocontent=None, notheme=None):
        self.source_location = source_location
        ## FIXME: proper error:
        assert content is not None or theme is not None
        self.content = content
        self.theme = theme
        self.if_content = if_content
        self.nocontent = self.convert_error('nocontent', nocontent)
        self.notheme = self.convert_error('notheme', notheme)

    def apply(self, content_doc, theme_doc, resource_fetcher, log):
        """Applies the action"""
        if not self.if_content_matches(content_doc, log):
            return
        for doc, selector, error, name in [
            (theme_doc, self.theme, self.notheme, 'theme'), 
            (content_doc, self.content, self.nocontent, 'content')]:
            self._apply_drop(doc, selector, error, name, log)

    def _apply_drop(self, doc, selector, error, name, log):
        if selector is None:
            return
        sel_type, els, attributes = self.select_elements(selector, doc, name=='theme')
        if not els:
            if error == 'abort':
                log.debug(
                    self, 'aborting %s because no %s element matches rule %s="%s"', 
                    name, name, name, selector)
                raise AbortTheme('No %s matches %s="%s"' % (name, name, selector))
            elif error == 'ignore':
                log_meth = log.debug
            else:
                log_meth = log.warn
            log_meth(
                self, 'skipping rule because no %s matches rule %s="%s"', 
                name, name, selector)
            return
        if sel_type == 'elements':
            for el in els:
                move_tail_upwards(el)
                el.getparent().remove(el)
            log.debug(
                self, 'Dropping %s %s', name, self.format_tags(els))
        elif sel_type == 'children':
            for el in els:
                el[:] = []
                el.text = ''
            log.debug(
                self, 'Dropping the children of %s %s', name, self.format_tags(els))
        elif sel_type == 'attributes':
            for el in els:
                attrib = el.attrib
                if attributes:
                    for attr_name in attributes:
                        if attr_name in attrib:
                            del attrib[attr_name]
                else:
                    attrib.clear()
            if attributes:
                log.debug(
                    self, 'Dropping the %s from the %s %s',
                    self.format_attribute_names(attributes), 
                    name, self.format_tags(els))
            else:
                log.debug(self, 'Dropping all the attributes of %s %s',
                          name, self.format_tags(els))
        elif sel_type == 'tag':
            for el in els:
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
            log.debug(
                self, 'Dropping the tag (flattening the element) of %s %s',
                name, self.format_tags(els))
        else:
            assert 0

    @classmethod
    def from_xml(cls, tag, source_location):
        """Parses and instantiates the class from an element"""
        content = cls.compile_selector(tag, 'content', source_location)
        theme = cls.compile_selector(tag, 'theme', source_location)
        if_content = cls.compile_selector(tag, 'if-content', source_location, invertable=True)
        return cls(source_location, content, theme, if_content=if_content,
                   nocontent=tag.get('nocontent'),
                   notheme=tag.get('notheme'))

    def clientside_actions(self, content_doc, log):
        self._apply_drop(content_doc, self.content, self.nocontent, 'content', log)
        return []

_actions['drop'] = Drop
            
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
    """
    Iterates over an element itself and all its ancestors (parent, grandparent, etc)
    """
    yield el
    for item in el.iterancestors():
        yield item

def mark_content_els(els):
    """
    Mark an element as originating from the content (this uses a special attribute)
    """
    for el in els:
        ## FIXME: maybe put something that is trackable to the rule
        ## that moved the element
        el.set(CONTENT_ATTRIB, '1')

def is_content_element(el):
    """
    Tests if the element came from the content (which includes if any of its ancestors)
    """
    ## FIXME: should this check children too?
    for parent in iter_self_and_ancestors(el):
        if parent.get(CONTENT_ATTRIB):
            return True
    return False

def remove_content_attribs(doc):
    """
    Remove the markers placed by :func:`mark_content_els`
    """
    for parent in doc.getiterator():
        if parent.get(CONTENT_ATTRIB, None) is not None:
            del parent.attrib[CONTENT_ATTRIB]


from lxml import etree
from deliverance import xinclude 
import copy
from deliverance import utils
from deliverance.utils import RuleSyntaxError
from deliverance.utils import RendererBase

class Renderer(RendererBase):
    """
    implements a deliverance renderer programmatically using 
    lxml api.  The rules, theme and content are all processed at 
    render time.
    """

    def __init__(self, theme, theme_uri,
                 rule, rule_uri,
                 reference_resolver=None):  
        """
        initializer. 

        theme: an lxml etree represenatation of the theme page 
        theme_uri: a uri referring to the theme page, used to 
                    make relative links in the theme absolute 
        rule: an lxml etree representation of the deliverance rules
               performed by this transformation 
        rule_uri: a uri representing the location of the rules document

        reference_resolver: a function taking a url a parse type and 
         and an encoding type returning the data referred to by the url 
         in the manner specified. if parse is set to 'xml' or 'html', 
         the result should be an lxml etree structure, otherwise if encoding 
         is specified, the data should be decoded using this encoding 
         before being returned. 
                
        """
        self.theme = self.fixup_links(theme, theme_uri)
        self.rules = rule
        self.rules_uri = rule_uri

        self.resolve_uri = reference_resolver

        # perform xincludes on the rules
        if self.resolve_uri:
            xinclude.include(self.rules, self.rules_uri, loader=self.resolve_uri)



        debug = self.rules.get("debug", None)
        if debug and debug.lower() == "true":
            self.debug = True
        else:
            self.debug = False


    def render(self, content):
        """
        content: an lxml etree structure representing the content to render 
        returns an lxml etree structure representing the result of the 
                transformation represented by this class performed on the 
                given content. 
        """
        result = copy.deepcopy(self.theme)
        input = self.aggregate(self.resolve_uri,self.rules,copy.deepcopy(content))
        self.apply_rules(self.rules, result, input)
        return result



    def apply_rules(self, rules, theme, content):
        """
        applies the deliverance rules given on the 
        theme and content given. drop rules are 
        run before any other rules. 
        rules, theme and content should be lxml etree 
        structures. 
        """
        drop_rules, other_rules = self.separate_drop_rules(rules)
        move_rules, other_rules = self.separate_move_rules(other_rules)

        # process all drop rules first 
        for rule in drop_rules:
            self.apply_rule(rule, theme, content) 

        # process all move rules next 
        for rule in move_rules: 
            self.apply_rule(rule,theme,content)

        # finally the rest
        for rule in other_rules:
            self.apply_rule(rule, theme, content)


    def apply_rule(self, rule, theme, content):
        """
        calls proper rule application function for 
        the rule given on the theme and content 
        given. rule, theme and content should be 
        lxml etree structures. 
        """
        if rule.tag == self.APPEND_RULE_TAG:
            self.apply_append(rule, theme, content)
        elif rule.tag == self.PREPEND_RULE_TAG:
            self.apply_prepend(rule, theme, content)
        elif rule.tag == self.REPLACE_RULE_TAG:
            self.apply_replace(rule, theme, content)
        elif rule.tag == self.COPY_RULE_TAG:
            self.apply_copy(rule, theme, content)
        elif rule.tag == self.APPEND_OR_REPLACE_RULE_TAG:
            self.apply_append_or_replace(rule, theme, content)
        elif rule.tag == self.DROP_RULE_TAG:
            self.apply_drop(rule, theme, content)
        elif rule.tag == self.SUBRULES_TAG:
            self.apply_rules(rule, theme, content)
        elif rule.tag is etree.Comment:
            pass
        else:
            raise RuleSyntaxError(
                "Rule %s (%s) not understood" % (
                    rule.tag, etree.tostring(rule)))

        # process possible "move" attribute 
        self.check_move(rule, theme, content)


    def check_move(self, rule, theme, content):
        if rule.get(self.RULE_MOVE_KEY, None) is None:
            return

        if rule.tag == self.SUBRULES_TAG or rule.tag == self.DROP_RULE_TAG: 
            e = self.format_error("rule does not support the move attribute", rule)
            self.add_to_body_start(theme, e)
            return

        # drop content elements if move was specified except when 
        # notheme='ignore' was specified and no theme elements were matched 
        theme_els = theme.xpath(rule.attrib.get(self.RULE_THEME_KEY)) 
        if (theme_els is not None and len(theme_els) > 0) or \
                rule.attrib.get(self.NOTHEME_KEY) != self.IGNORE_KEYWORD:
            self.drop_els(content, content.xpath(self.get_content_xpath(rule)))


    def apply_append(self,rule,theme,content):
        """
        function that performs the deliverance "append" 
        rule given by rule on the theme and content given. 
        see deliverance specification 
        """
        theme_el = self.get_theme_el(rule, theme)
        if theme_el is None:
            return 

        content_els = copy.deepcopy(
            content.xpath(self.get_content_xpath(rule)))

        if len(content_els) == 0:
            if rule.get(self.NOCONTENT_KEY) != 'ignore':
                self.add_to_body_start(
                    theme, self.format_error("no content matched", rule))
            return 

        if self.debug:
            self.debug_append(theme_el, content_els, rule)
            return 

        non_text_els = self.elements_in(content_els)
        self.strip_tails(non_text_els)        

        # the xpath may return a mixture of strings and elements, handle strings 
        # by attaching them to the proper element 
        if (type(content_els[0]) is type(str())):
            # if the element we're appending to has children, the text is 
            # appended to the tail of the last child. 
            if len(theme_el): 
                if theme_el[-1].tail:
                    theme_el[-1].tail += content_els[0]
                else:
                    theme_el[-1].tail = content_els[0]
            # otherwise, the text is appeded to the text attribute of the 
            # element we're appending to 
            else: 
                if theme_el.text:
                    theme_el.text += content_els[0]
                else:
                    theme_el.text = content_els[0]
            
        self.attach_tails(content_els)
        theme_el.extend(non_text_els)

    def debug_append(self, theme_el, content_els, rule):
        """
        debugging variant of the deliverance "append" 
        rule (run when the rule has debugging enabled) 
        see deliverance specification 
        """
        comment_before,comment_after = self.make_debugging_comments(rule)
        content_els[:0] = [comment_before]
        content_els.append(comment_after)

        non_text_els = self.elements_in(content_els)
        self.strip_tails(non_text_els)        
            
        self.attach_tails(content_els)
        theme_el.extend(non_text_els)
        


    def apply_prepend(self, rule, theme, content):
        """
        function that performs the deliverance "prepend" 
        rule given by rule on the theme and content given. 
        see deliverance specification 
        """
        theme_el = self.get_theme_el(rule, theme)
        if theme_el is None:
            return 

        xpath = self.get_content_xpath(rule)
        content_els = copy.deepcopy(content.xpath(xpath))

        if len(content_els) == 0:
            if rule.attrib.get(self.NOCONTENT_KEY) != 'ignore':
                self.add_to_body_start(
                    theme, self.format_error("no content matched", rule))
            return 

        if self.debug:
            self.debug_prepend(theme_el, content_els, rule)
            return 

        non_text_els = self.elements_in(content_els)
        
        # if we only get some text, just tack it on and return 
        if len(non_text_els) == 0 and type(content_els[0]) is type(str()): 
            if theme_el.text:
                theme_el.text = content_els[0] + theme_el.text
            else:
                theme_el.text = content_els[0]
            return 

        # here we have some elements and possibly some text 

        self.strip_tails(non_text_els)

        # the xpath may return a mixture of strings and elements, handle the 
        # first string by making it the text of the parent element. In any 
        # case if the parent element has text, we need put it after the 
        # elements we're prepending so we save it here
        old_start_text = theme_el.text 
        if (type(content_els[0]) is type(str())):
            theme_el.text = content_els[0]
        else:
            theme_el.text = None
            
        self.attach_tails(content_els)
        theme_el[:0] = non_text_els

        # tack on the previous text of the parent element 
        if old_start_text:
            if (non_text_els[-1].tail):
                non_text_els[-1].tail += old_start_text
            else:
                non_text_els[-1].tail = old_start_text

    def debug_prepend(self, theme_el, content_els, rule):        
        """
        debugging variant of the deliverance "prepend" 
        rule (run when the rule has debugging enabled) 
        see deliverance specification 
        """

        comment_before, comment_after = self.make_debugging_comments(rule)
        content_els[:0] = [comment_before]
        content_els.append(comment_after)

        if theme_el.text:
            content_els.append(theme_el.text)
            theme_el.text = None

        non_text_els = self.elements_in(content_els)
        self.strip_tails(non_text_els)                
        self.attach_tails(content_els)

        theme_el[:0] = non_text_els

    def apply_replace(self, rule, theme, content):
        """
        function that performs the deliverance "replace" 
        rule given by rule on the theme and content given. 
        see deliverance specification 
        """
        theme_el = self.get_theme_el(rule, theme)
        if theme_el is None:
            return 

        content_els = copy.deepcopy(
            content.xpath(self.get_content_xpath(rule)))

        if len(content_els) == 0:
            if rule.attrib.get(self.NOCONTENT_KEY) != 'ignore':
                self.add_to_body_start(
                    theme, self.format_error("no content matched", rule))            
            return       

        if theme_el.getparent() is None:
            self.add_to_body_start(
                theme, self.format_error("cannot replace whole theme", rule))            
            return
            

        if self.debug:
            self.debug_replace(theme_el, content_els, rule)
            return 

        self.replace_many(theme_el,content_els)

    def debug_replace(self,theme_el,content_els,rule):
        """
        debugging variant of the deliverance "replace" 
        rule (run when the rule has debugging enabled) 
        see deliverance specification 
        """
        comment_before, comment_after = self.make_debugging_comments(rule)
        content_els[:0] = [comment_before]
        content_els.append(comment_after)

        non_text_els = self.elements_in(content_els)
        self.strip_tails(non_text_els)                    
        self.attach_tails(content_els)

        parent = theme_el.getparent()

        if theme_el.tail:
            comment_after.tail = theme_el.tail 

        parent.replace(theme_el, non_text_els[0])
        i = parent.index(non_text_els[0])
        parent[i+1:i+1] = non_text_els[1:]
        
    def _xpath_copy(self, source, xpath):
        """
        helper function that returns a deep copy of the 
        element referred to by 'xpath' in the 'source'
        document given. raises XPathSyntaxError if 
        xpath is invalid. 
        """
        try:
            found_element = source.xpath(xpath)
        except etree.XPathSyntaxError, e:
            raise etree.XPathSyntaxError('%s (in expression %r)' % (e, xpath))
        return copy.deepcopy(found_element)

    def apply_copy(self, rule, theme, content):
        """
        function that performs the deliverance "copy" 
        rule given by rule on the theme and content given. 
        see deliverance specification 
        """
        theme_el = self.get_theme_el(rule,theme)
        if theme_el is None:
            return

        content_els = self._xpath_copy(content, self.get_content_xpath(rule))

        if len(content_els) == 0:
            if rule.attrib.get(self.NOCONTENT_KEY) != 'ignore':
                self.add_to_body_start(
                    theme, self.format_error("no content matched", rule))
            return 

        non_text_els = self.elements_in(content_els)
        self.strip_tails(non_text_els)
        # attach any leading matched text as the text of the element 
        # we're copying into 
        if (type(content_els[0]) is type(str())):
            theme_el.text = content_els[0]
        # otherwise knock out any existing text 
        else:
            theme_el.text = None

        self.attach_tails(content_els)
        theme_el[:] = non_text_els  

        if self.debug:
            comment_before,comment_after = self.make_debugging_comments(rule)
            if theme_el.text:
                comment_before.text = theme_el.text 
            theme_el[0:0] = [comment_before]
            theme_el.append(comment_after)
            

    def apply_append_or_replace(self, rule, theme, content):
        """
        function that performs the deliverance "append-or-replace" 
        rule given by rule on the theme and content given. 
        see deliverance specification 
        """
        theme_el = self.get_theme_el(rule, theme)
        if theme_el is None:
            return 

        content_xpath = self.get_content_xpath(rule)
        remove_tag = self.get_tag_from_xpath(content_xpath)

        if remove_tag is None:
            self.add_to_body_start(
                theme, self.format_error("invalid xpath for content", rule=rule))
            return

        content_els = copy.deepcopy(content.xpath(content_xpath))        
 
        if len(content_els) == 0:
            if rule.attrib.get(self.NOCONTENT_KEY) != 'ignore':
                self.add_to_body_start(
                    theme, self.format_error("no content matched", rule))
            return 

        for el in theme_el:
            if el.tag == remove_tag:
                self.attach_text_to_previous(el, el.tail)
                theme_el.remove(el)


        if self.debug:
            self.debug_append(theme_el, content_els, rule)
            return 

        self.strip_tails(content_els)
        theme_el.extend(content_els)



    def drop_els(self,doc,els): 
        """
        helper to drop a list of elements without losing 
        surrounding text 
        """
        removed = 0
        for el in els: 
            self.attach_text_to_previous(el,el.tail)
            el.getparent().remove(el)
            removed += 1
        return removed

    
    def apply_drop(self, rule, theme, content):        
        """
        function that performs the deliverance "drop" 
        rule given by rule on the theme and content given. 
        see deliverance specification 
        """
        content_drop_xp = self.get_content_xpath(rule)
        theme_drop_xp = rule.attrib.get(self.RULE_THEME_KEY,None)
        
        if (content_drop_xp is None and theme_drop_xp is None): 
            self.add_to_body_start(
                theme, self.format_error("No content or theme elements specified.",rule))
            return
                
        if content_drop_xp: 
            num_dropped = self.drop_els(self,content.xpath(content_drop_xp))
            if num_dropped == 0 and not rule.attrib.get(self.NOCONTENT_KEY,None) == self.IGNORE_KEYWORD: 
                self.add_to_body_start(
                    theme, self.format_error("no content matched", rule))

        if theme_drop_xp: 
            num_dropped = self.drop_els(self,theme.xpath(theme_drop_xp))
            if num_dropped == 0 and not rule.attrib.get(self.NOTHEME_KEY,None) == self.IGNORE_KEYWORD: 
                self.add_to_body_start(
                    theme, self.format_error("no theme matched", rule))


    def make_debugging_comments(self, rule):
        """
        returns a pair of comments for insertion before and 
        after work done by the rule given during debugging. 
        """
        comment_before = etree.Comment("Deliverance: applying rule %s" % etree.tostring(rule))
        comment_after = etree.Comment("Deliverance: done applying rule %s" % etree.tostring(rule))
        return comment_before, comment_after

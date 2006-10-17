from lxml import etree
import xinclude 
import copy
import utils
from utils import RuleSyntaxError
from utils import RendererBase

class Renderer(RendererBase):
    """
    implements a deliverance renderer programmatically using 
    lxml api.  The rules, theme and content are all processed at 
    render time.
    """

    def __init__(self, theme, theme_uri,
                 rule, rule_uri,
                 reference_resolver=None):  
        self.theme = self.fixup_links(theme, theme_uri)
        self.rules = rule
        self.rules_uri = rule_uri
        # perform xincludes on the rules
        if reference_resolver:
            xinclude.include(self.rules, self.rules_uri, loader=reference_resolver)

        debug = self.rules.get("debug", None)
        if debug and debug.lower() == "true":
            self.debug = True
        else:
            self.debug = False


    def render(self, content):
        result = copy.deepcopy(self.theme)
        input = copy.deepcopy(content)
        self.apply_rules(self.rules,result,input)
        return result


    def apply_rules(self,rules,theme,content):
        for rule in rules:
            self.apply_rule(rule,theme,content)


    def apply_rule(self,rule,theme,content):
        if rule.tag == self.APPEND_RULE_TAG:
            self.apply_append(rule,theme,content)
        elif rule.tag == self.PREPEND_RULE_TAG:
            self.apply_prepend(rule,theme,content)
        elif rule.tag == self.REPLACE_RULE_TAG:
            self.apply_replace(rule,theme,content)
        elif rule.tag == self.COPY_RULE_TAG:
            self.apply_copy(rule,theme,content)
        elif rule.tag == self.APPEND_OR_REPLACE_RULE_TAG:
            self.apply_append_or_replace(rule,theme,content)
        elif rule.tag == self.SUBRULES_TAG:
            self.apply_rules(rule,theme,content)
        elif rule.tag is etree.Comment:
            pass
        else:
            raise RuleSyntaxError(
                "Rule %s (%s) not understood" % (
                    rule.tag, etree.tostring(rule)))

    def apply_append(self,rule,theme,content):
        theme_el = self.get_theme_el(rule,theme)
        if theme_el is None:
            return 

        content_els = copy.deepcopy(content.xpath(rule.attrib[self.RULE_CONTENT_KEY]))

        if len(content_els) == 0:
            if rule.get(self.NOCONTENT_KEY) != 'ignore':
                self.add_to_body_start(theme, self.format_error("no content matched", rule))
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
        
        comment_before,comment_after = self.make_debugging_comments(rule)
        content_els[:0] = [comment_before]
        content_els.append(comment_after)

        non_text_els = self.elements_in(content_els)
        self.strip_tails(non_text_els)        
            
        self.attach_tails(content_els)
        theme_el.extend(non_text_els)
        


    def apply_prepend(self,rule,theme,content):
        theme_el = self.get_theme_el(rule,theme)
        if theme_el is None:
            return 

        content_els = copy.deepcopy(content.xpath(rule.attrib[self.RULE_CONTENT_KEY]))

        if len(content_els) == 0:
            if rule.attrib.get(self.NOCONTENT_KEY) != 'ignore':
                self.add_to_body_start(theme, self.format_error("no content matched", rule))
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
        
        comment_before,comment_after = self.make_debugging_comments(rule)
        content_els[:0] = [comment_before]
        content_els.append(comment_after)

        if theme_el.text:
            content_els.append(theme_el.text)
            theme_el.text = None

        non_text_els = self.elements_in(content_els)
        self.strip_tails(non_text_els)                
        self.attach_tails(content_els)

        theme_el[:0] = non_text_els

    def apply_replace(self,rule,theme,content):
        theme_el = self.get_theme_el(rule,theme)
        if theme_el is None:
            return 

        content_els = copy.deepcopy(content.xpath(rule.attrib[self.RULE_CONTENT_KEY]))

        if len(content_els) == 0:
            if rule.attrib.get(self.NOCONTENT_KEY) != 'ignore':
                self.add_to_body_start(theme, self.format_error("no content matched", rule))            
            return       

        if self.debug:
            self.debug_replace(theme_el,content_els,rule)
            return 

        non_text_els = self.elements_in(content_els)
        self.strip_tails(non_text_els)


        # the xpath may return a mixture of strings and elements, handle strings 
        # by attaching them to the proper element 
        if (type(content_els[0]) is type(str())):
            # text must be appended to the tail of the most recent sibling or appended 
            # to the text of the parent of the replaced element
            self.attach_text_to_previous(theme_el,content_els[0])

        if len(non_text_els) == 0:
            self.attach_text_to_previous(theme_el,theme_el.tail)
            theme_el.getparent().remove(theme_el)
            return
            
        self.attach_tails(content_els)

        # this tail, if there is one, should stick around 
        preserve_tail = non_text_els[0].tail 

        self.replace_element(theme_el, non_text_els[0])
        temptail = non_text_els[0].tail 
        non_text_els[0].tail = None
        parent = non_text_els[0].getparent()
        i = parent.index(non_text_els[0])
        parent[i+1:i+1] = non_text_els[1:]

        if non_text_els[-1].tail:
            non_text_els[-1].tail += temptail
        else:
            non_text_els[-1].tail = temptail
        
        # tack in any preserved tail we stored above
        if preserve_tail:
            if non_text_els[0].tail:
                non_text_els[0].tail = preserve_tail + non_text_els[0].tail
            else:
                non_text_els[0].tail = preserve_tail

    def debug_replace(self,theme_el,content_els,rule):
        comment_before,comment_after = self.make_debugging_comments(rule)
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
        

    def apply_copy(self,rule,theme,content):
        theme_el = self.get_theme_el(rule,theme)
        if theme_el is None:
            return 

        content_els = copy.deepcopy(content.xpath(rule.attrib[self.RULE_CONTENT_KEY]))

        if len(content_els) == 0:
            if rule.attrib.get(self.NOCONTENT_KEY) != 'ignore':
                self.add_to_body_start(theme, self.format_error("no content matched", rule))
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
            parent = theme_el.getparent()
            index = parent.index(theme_el)
            parent.insert(index-1,comment_before)
            parent.insert(index+2,comment_after)
            comment_after.tail = theme_el.tail
            theme_el.tail = None
            

    def apply_append_or_replace(self,rule,theme,content):
        theme_el = self.get_theme_el(rule,theme)
        if theme_el is None:
            return 

        content_xpath = rule.attrib[self.RULE_CONTENT_KEY]
        remove_tag = self.get_tag_from_xpath(content_xpath)

        if remove_tag is None:
            self.add_to_body_start(theme,self.format_error("invalid xpath for content", rule=rule))
            return

        content_els = copy.deepcopy(content.xpath(content_xpath))        
 
        if len(content_els) == 0:
            if rule.attrib.get(self.NOCONTENT_KEY) != 'ignore':
                self.add_to_body_start(theme, self.format_error("no content matched", rule))
            return 

        for el in theme_el:
            if el.tag == remove_tag:
                self.attach_text_to_previous(el,el.tail)
                theme_el.remove(el)


        if self.debug:
            self.debug_append(theme_el, content_els, rule)
            return 

        self.strip_tails(content_els)
        theme_el.extend(content_els)



    def elements_in(self, els):
        """
        return a list containing elements from els which are not strings 
        """
        return [x for x in els if type(x) is not type(str())]
            


    def strip_tails(self, els):
        for el in els:
            el.tail = None


    def attach_tails(self,els):
        """
        whereever an lxml element in the list is followed by 
        a string, set the tail of the lxml element to the string 
        """
        for index,el in enumerate(els): 
            # if we run into a string after the current element, 
            # attach it to the current element as the tail 
            if (type(el) is not type(str()) and 
                index + 1 < len(els) and 
                type(els[index+1]) is type(str())):
                el.tail = els[index+1]   


    def make_debugging_comments(self, rule):
        comment_before = etree.Comment("Deliverance: applying rule %s" % etree.tostring(rule))
        comment_after = etree.Comment("Deliverance: done applying rule %s" % etree.tostring(rule))
        return comment_before, comment_after

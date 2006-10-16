from lxml import etree
import xinclude
import copy 
import re
import utils
from utils import RuleSyntaxError
from utils import RendererBase


xslt_wrapper_skel = """
<xsl:transform version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
  <xsl:template match="/">
    <!-- theme goes here --> 
  </xsl:template>
</xsl:transform>"""


nsmap = {
    "dv": "http://www.plone.org/deliverance",
    "html": "http://www.w3.org/1999/xhtml",
    "xsl": "http://www.w3.org/1999/XSL/Transform",
}

class Renderer(RendererBase):
    """
    implements a deliverance renderer by preprocessing the rules and theme 
    into an xslt transform at initialization time and applying it to the 
    content at render time
    """

    def __init__(self,theme,theme_uri,rule, rule_uri, reference_resolver=None):
        theme_copy = copy.deepcopy(theme)
        self.rules = rule
        self.rules_uri = rule_uri

        self.fixup_links(theme_copy,theme_uri)
        self.xsl_escape_comments(theme_copy)

        if reference_resolver:
            xinclude.include(self.rules, self.rules_uri, loader=reference_resolver)

        debug = self.rules.get("debug", None)
        if debug and debug.lower() == "true":
            self.debug = True
        else:
            self.debug = False

        self.apply_rules(self.rules,theme_copy)
        xslt_wrapper = etree.XML(xslt_wrapper_skel)
        insertion_point = xslt_wrapper.xpath("//xsl:transform/xsl:template[@match='/']",
                                             nsmap)[0]
        insertion_point.append(theme_copy)

        self.transform = etree.XSLT(xslt_wrapper)
    
        

    def render(self,content):
        if content:
            return self.transform(content).getroot()
        else:
            return self.transform(etree.Element("dummy")).getroot()


    def apply_rules(self,rules,theme):
        for rule in rules:
            self.apply_rule(rule,theme)

    def apply_rule(self,rule,theme):
        if rule.tag == self.APPEND_RULE_TAG:
            self.apply_append(rule,theme)
        elif rule.tag == self.PREPEND_RULE_TAG:
            self.apply_prepend(rule,theme)
        elif rule.tag == self.REPLACE_RULE_TAG:
            self.apply_replace(rule,theme)
        elif rule.tag == self.COPY_RULE_TAG:
            self.apply_copy(rule,theme)
        elif rule.tag == self.APPEND_OR_REPLACE_RULE_TAG:
            self.apply_append_or_replace(rule,theme)
        elif rule.tag == self.SUBRULES_TAG:
            self.apply_rules(rule,theme)
        elif rule.tag is etree.Comment:
            pass
        else:
            raise RuleSyntaxError(
                "Rule %s (%s) not understood" % (
                    rule.tag, etree.tostring(rule)))

    def apply_append(self,rule,theme):
        theme_el = self.get_theme_el(rule,theme)
        if theme_el is None:
            return 

        # add an element that produces an error in the theme if 
        # no content is matched 
        self.add_conditional_missing_content_error(theme,rule)


        copier = etree.Element("{%s}copy-of" % nsmap["xsl"])
        copier.set("select",rule.attrib[self.RULE_CONTENT_KEY])        

        self.debug_append(theme_el, copier, rule)


    def apply_prepend(self,rule,theme):
        theme_el = self.get_theme_el(rule,theme)
        if theme_el is None:
            return 

        # add an element that produces an error in the theme if 
        # no content is matched 
        self.add_conditional_missing_content_error(theme,rule)

        copier = etree.Element("{%s}copy-of" % nsmap["xsl"])

        copier.set("select",rule.attrib[self.RULE_CONTENT_KEY])        

        self.debug_prepend(theme_el, copier, rule)


    def apply_replace(self,rule,theme):
        theme_el = self.get_theme_el(rule,theme)
        if theme_el is None:
            return 

        self.add_conditional_missing_content_error(theme,rule)      

        copier = etree.Element("{%s}copy-of" % nsmap["xsl"])
        copier.set("select",rule.attrib[self.RULE_CONTENT_KEY])


        # if content is matched, replace the theme element, otherwise, keep the
        # theme element 
        choose = self.make_when_otherwise("count(%s)=0" % 
                                          rule.attrib[self.RULE_CONTENT_KEY], 
                                          copy.deepcopy(theme_el), 
                                          copier)

        self.debug_replace(theme_el,choose,rule)


    def apply_copy(self,rule,theme):
        theme_el = self.get_theme_el(rule,theme)
        if theme_el is None:
            return 

        # add an element that produces an error in the theme if 
        # no content is matched 
        self.add_conditional_missing_content_error(theme,rule)

        # create an element that is like the target theme element 
        # with its children replaced by an xsl copy element 
        copy_theme_el = copy.deepcopy(theme_el)
        del(copy_theme_el[:])
        copy_theme_el.text = None
        copier = etree.SubElement(theme_el,
                                    "{%s}copy-of" % nsmap["xsl"])
        copier.set("select",rule.attrib[self.RULE_CONTENT_KEY])  
        copy_theme_el.append(copier)

        # create a copy of the current theme element 
        normal_theme_el = copy.deepcopy(theme_el)

        # create an xsl choose element that picks between them based 
        # on whether content was matched 
        choose = self.make_when_otherwise("count(%s)=0" % 
                                          rule.attrib[self.RULE_CONTENT_KEY], 
                                          normal_theme_el, 
                                          copy_theme_el)
        self.debug_replace(theme_el,choose,rule)
        copy_theme_el.tail = None
        normal_theme_el.tail = None
        

   
    def apply_append_or_replace(self,rule,theme):
        theme_el = self.get_theme_el(rule,theme)
        if theme_el is None:
            return 
        remove_tag = self.get_tag_from_xpath(rule.attrib[self.RULE_CONTENT_KEY])
        if remove_tag is None:
            self.add_to_body_start(theme,self.format_error("invalid xpath for content", rule=rule))
            return 

        # add an element that produces an error in the theme if 
        # no content is matched 
        self.add_conditional_missing_content_error(theme,rule)

        for el in theme_el:
            if el.tag == remove_tag:
                conditional = etree.Element("{%s}if" % nsmap["xsl"])
                conditional.set("test","count(%s) = 0" % 
                                rule.attrib[self.RULE_CONTENT_KEY])
                conditional.append(copy.deepcopy(el))
                self.replace_element(el,conditional)
 
        copier = etree.Element("{%s}copy-of" % nsmap["xsl"])
        copier.set("select",rule.attrib[self.RULE_CONTENT_KEY])
   
        self.debug_append(theme_el, copier, rule)


    def xsl_escape_comments(self,doc):
        """
        replaces comment nodes with xsl:comment nodes so they will 
        appear in the result of a transform rather than being 
        treated as comments in the transform 
        """
        comment_nodes = doc.xpath('//comment()')
        for c in comment_nodes:
            escaped = etree.Element("{%s}comment" % nsmap["xsl"])
            escaped.text = c.text 
            self.replace_element(c,escaped)
    
    def add_conditional_missing_content_error(self,theme,rule):
        """
        adds a node to the body of theme which produces an error 
        message if no content is matched by a rule given 
        during the transformation; no message is produced
        if nocontent='ignore' attribute is set
        """
        if rule.get(self.NOCONTENT_KEY) == 'ignore':
            return

        err = self.format_error("no content matched", rule)
        if err:
            conditional = etree.Element("{%s}if" % nsmap["xsl"])
            conditional.set("test", "count(%s)=0" % rule.attrib[self.RULE_CONTENT_KEY])
            conditional.append(err)
            self.add_to_body_start(theme,conditional)
        

    def make_when_otherwise(self, test, whenbody, otherwisebody):
        """
        makes a conditional xlst node. when placed into a document, 
        if the xslt expression represented by the string test evaluates 
        to true, whenbody is produced, if false, otherwise body is produced 
        """
        choose = etree.Element("{%s}choose" % nsmap["xsl"])
        when = etree.Element("{%s}when" % nsmap["xsl"])
        when.set("test", test)
        when.append(copy.deepcopy(whenbody))
        otherwise = etree.Element("{%s}otherwise" % nsmap["xsl"])
        otherwise.append(otherwisebody)
        choose.append(when)
        choose.append(otherwise)
        return choose


    def debug_append(self, parent, child, rule):        
        """
        helper method for appending a node, if debugging is enabled, 
        the appended node is wrapped in comments referring to the 
        rule that performed the append 
        """
        if self.debug:
            comment_before,comment_after = self.make_debugging_comments(rule)
            parent.append(comment_before)
            parent.append(child)
            parent.append(comment_after)
        else:
            parent.append(child)


    def debug_replace(self, old_el, new_el, rule):
        """
        helper method for replacing a node, if debugging is enabled, 
        the new node is wrapped in comments referring to the 
        rule that performed the replace  
        """
        self.replace_element(old_el, new_el)
        
        if self.debug:
            parent = new_el.getparent()
            index = parent.index(new_el)
            
            comment_before,comment_after = self.make_debugging_comments(rule)
            comment_after.tail = new_el.tail
            new_el.tail = None

            parent.insert(index, comment_before)
            parent.insert(index+2, comment_after)

    def debug_prepend(self, parent, child, rule):
        """
        helper method for prepending a node, if debugging is enabled, 
        the prepended node is wrapped in comments referring to the 
        rule that performed the append 
        """
        parent.insert(0,child)
        child.tail = parent.text
        parent.text = None

        if self.debug:
            comment_before,comment_after = self.make_debugging_comments(rule)
            comment_after.tail = child.tail
            child.tail = None

            parent.insert(0, comment_before)
            parent.insert(2, comment_after)


    def make_debugging_comments(self, rule):
        """
        helper method which prepares two xslt:comment nodes used 
        for wrapping inserted content nodes during debugging
        """
        comment_before = etree.Element("{%s}comment" % nsmap["xsl"])
        comment_before.text = "Deliverance: applying rule %s" % etree.tostring(rule)
        comment_after = etree.Element("{%s}comment" % nsmap["xsl"])
        comment_after.text = "Deliverance: done applying rule %s" % etree.tostring(rule)
        return comment_before, comment_after

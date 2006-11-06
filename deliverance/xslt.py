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

xslt_dropper_skel = """
<xsl:transform version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">

  <!-- match nodes that do dropping are inserted here --> 

  <xsl:template match="node()|@*">
    <xsl:copy>
      <xsl:apply-templates select="node()|@*"/>
    </xsl:copy>
  </xsl:template> 

</xsl:transform>
"""

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

    def __init__(self, theme, theme_uri, rule, rule_uri, reference_resolver=None):
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
         in the manner specified. if parse is set to 'xml', the result 
         should be an lxml etree structure, otherwise if encoding 
         is specified, the data should be decoded using this encoding 
         before being returned. 
                
        """
        theme_copy = copy.deepcopy(theme)
        self.rules = rule
        self.rules_uri = rule_uri

        self.fixup_links(theme_copy, theme_uri)
        self.xsl_escape_comments(theme_copy)

        if reference_resolver:
            xinclude.include(self.rules, self.rules_uri, loader=reference_resolver)

        debug = self.rules.get("debug", None)
        if debug and debug.lower() == "true":
            self.debug = True
        else:
            self.debug = False

        self.transform_drop = None
        self.apply_rules(self.rules,theme_copy)
    
        xslt_wrapper = etree.XML(xslt_wrapper_skel)
        insertion_point = xslt_wrapper.xpath("//xsl:transform/xsl:template[@match='/']",
                                             nsmap)[0]
        insertion_point.append(theme_copy)

        self.transform = etree.XSLT(xslt_wrapper)
    
        

    def render(self, content):
        """
        content: an lxml etree structure representing the content to render 
        returns an lxml etree structure representing the result of the 
                transformation represented by this class performed on the 
                given content. 
        """
        if content:
            if self.transform_drop:
                content = self.transform_drop(content)

            return self.transform(content).getroot()

        else:
            return self.transform(etree.Element("dummy")).getroot()


    def apply_rules(self, rules, theme):
        """
        prepares an xslt transforms which accpet a content document. 
        The transforms represent the application of 
        the rules given in the context of the theme given. 
        """
        drop_rules, other_rules = self.separate_drop_rules(rules)

        if len(drop_rules):
            self.xslt_dropper = etree.XML(xslt_dropper_skel)
            for rule in drop_rules:
                self.apply_drop(rule, theme)
            self.transform_drop = etree.XSLT(self.xslt_dropper)

        for rule in other_rules:
            self.apply_rule(rule, theme)


    def apply_rule(self, rule, theme):
        """
        dispatch to proper rule handling function for 
        the rule given. 
        """
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
        elif rule.tag == self.DROP_RULE_TAG:
            self.apply_drop(rule,theme)
        elif rule.tag == self.SUBRULES_TAG:
            self.apply_rules(rule,theme)
        elif rule.tag is etree.Comment:
            pass
        else:
            raise RuleSyntaxError(
                "Rule %s (%s) not understood" % (
                    rule.tag, etree.tostring(rule)))

    def apply_append(self, rule, theme):
        """
        prepare transform elements for "append" rule 
        """
        theme_el = self.get_theme_el(rule, theme)
        if theme_el is None:
            return 

        # add an element that produces an error in the theme if 
        # no content is matched 
        self.add_conditional_missing_content_error(theme, rule)


        copier = etree.Element("{%s}copy-of" % nsmap["xsl"])
        copier.set("select",rule.attrib[self.RULE_CONTENT_KEY])        

        self.debug_append(theme_el, copier, rule)


    def apply_prepend(self, rule, theme):
        """
        prepare transform elements for "prepend" rule 
        """
        theme_el = self.get_theme_el(rule, theme)
        if theme_el is None:
            return 

        # add an element that produces an error in the theme if 
        # no content is matched 
        self.add_conditional_missing_content_error(theme, rule)

        copier = etree.Element("{%s}copy-of" % nsmap["xsl"])

        copier.set("select",rule.attrib[self.RULE_CONTENT_KEY])        

        self.debug_prepend(theme_el, copier, rule)


    def apply_replace(self, rule, theme):
        """
        prepare transform elements for "replace" rule 
        """
        theme_el = self.get_theme_el(rule, theme)
        if theme_el is None:
            return 

        if theme_el.getparent() is None:
            self.add_to_body_start(
                theme, self.format_error("cannot replace whole theme", rule))            
            return

        self.add_conditional_missing_content_error(theme, rule)      

        copier = etree.Element("{%s}copy-of" % nsmap["xsl"])
        copier.set("select",rule.attrib[self.RULE_CONTENT_KEY])


        # if content is matched, replace the theme element, otherwise, keep the
        # theme element 
        choose = self.make_when_otherwise("count(%s)=0" % 
                                          rule.attrib[self.RULE_CONTENT_KEY], 
                                          copy.deepcopy(theme_el), 
                                          copier)

        self.debug_replace(theme_el,choose,rule)


    def apply_copy(self, rule, theme):
        """
        prepare transform elements for "prepend" rule 
        """

        theme_el = self.get_theme_el(rule, theme)
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
        self.debug_replace(theme_el, choose,rule)
        copy_theme_el.tail = None
        normal_theme_el.tail = None
        

   
    def apply_append_or_replace(self, rule, theme):
        """
        prepare transform elements for "append-or-replace" rule 
        """
        theme_el = self.get_theme_el(rule, theme)
        if theme_el is None:
            return 
        remove_tag = self.get_tag_from_xpath(rule.attrib[self.RULE_CONTENT_KEY])
        if remove_tag is None:
            self.add_to_body_start(theme,self.format_error("invalid xpath for content", rule=rule))
            return 

        # add an element that produces an error in the theme if 
        # no content is matched 
        self.add_conditional_missing_content_error(theme, rule)

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


    def apply_drop(self, rule, theme):
        """
        prepare transform elements for "drop" rule 
        """
        if self.RULE_THEME_KEY in rule.attrib:
            if len(theme.xpath(rule.attrib[self.RULE_THEME_KEY])) == 0:
                if rule.get(self.NOCONTENT_KEY) == 'ignore':
                    return 
                else:
                    e = self.format_error("no theme matched", rule)
                    self.add_to_body_start(theme, e)
                    return 
                    
            for el in theme.xpath(rule.attrib[self.RULE_THEME_KEY]):
                self.debug_drop(el,rule)
                self.attach_text_to_previous(el, el.tail)
                el.getparent().remove(el)

        if self.RULE_CONTENT_KEY in rule.attrib:
            drop_template = etree.Element("{%s}template" % nsmap["xsl"])
            drop_template.set("match", rule.attrib[self.RULE_CONTENT_KEY])
            self.xslt_dropper[0:0] = [drop_template]

            # add an element that produces an error if 
            # no content is matched 
            self.add_conditional_missing_content_error(theme,rule)





    def xsl_escape_comments(self, doc):
        """
        replaces comment nodes with xsl:comment nodes so they will 
        appear in the result of a transform rather than being 
        treated as comments in the transform 
        """
        comment_nodes = doc.xpath('//comment()')
        for c in comment_nodes:
            escaped = etree.Element("{%s}comment" % nsmap["xsl"])
            escaped.text = c.text 
            self.replace_element(c, escaped)
    
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
            self.add_to_body_start(theme, conditional)
        

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

    def debug_drop(self, el, rule):
        """
        helper method for deleting a node, if debugging is enabled, 
        comments are inserted referring to the 
        rule that performed the drop  
        """
        if self.debug:
            parent = el.getparent()
            index = parent.index(el)
            
            comment_before,comment_after = self.make_debugging_comments(rule)

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

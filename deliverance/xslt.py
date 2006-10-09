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

    def __init__(self,theme,theme_uri,rules,reference_resolver=None):
        theme_copy = copy.deepcopy(theme)

        self.fixup_links(theme_copy,theme_uri)
        self.remove_http_equiv_metas(theme_copy)
        self.xsl_escape_comments(theme_copy)

        if reference_resolver:
            xinclude.include(rules,loader=reference_resolver)
        self.apply_rules(rules,theme_copy)
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

        copier = etree.SubElement(theme_el,
                                    "{%s}copy-of" % nsmap["xsl"])
        copier.set("select",rule.attrib[self.RULE_CONTENT_KEY])        

    def apply_prepend(self,rule,theme):
        theme_el = self.get_theme_el(rule,theme)
        if theme_el is None:
            return 

        copier = etree.Element("{%s}copy-of" % nsmap["xsl"])

        copier.set("select",rule.attrib[self.RULE_CONTENT_KEY])        

        theme_el.insert(0,copier)
        copier.tail = theme_el.text
        theme_el.text = None

    def apply_replace(self,rule,theme):
        theme_el = self.get_theme_el(rule,theme)
        if theme_el is None:
            return 
      
        copier = etree.Element("{%s}copy-of" % nsmap["xsl"])
        copier.set("select",rule.attrib[self.RULE_CONTENT_KEY])

        self.replace_element(theme_el,copier)


    def apply_copy(self,rule,theme):
        theme_el = self.get_theme_el(rule,theme)
        if theme_el is None:
            return 

        del(theme_el[:])
        theme_el.text = None
        copier = etree.SubElement(theme_el,
                                    "{%s}copy-of" % nsmap["xsl"])
        copier.set("select",rule.attrib[self.RULE_CONTENT_KEY])        
        

   
    def apply_append_or_replace(self,rule,theme):
        theme_el = self.get_theme_el(rule,theme)
        if theme_el is None:
            return 
        remove_tag = self.get_tag_from_xpath(rule.attrib[self.RULE_CONTENT_KEY])
        if remove_tag is None:
            self.add_to_body_start(theme,self.format_error("invalid xpath for content", rule=rule))
            return 

        for el in theme_el:
            if el.tag == remove_tag:
                theme_el.remove(el)
        copier = etree.SubElement(theme_el,
                                    "{%s}copy-of" % nsmap["xsl"])
        copier.set("select",rule.attrib[self.RULE_CONTENT_KEY])        
   

    def xsl_escape_comments(self,doc):
        """
        replaces comment nodes with xsl:comment nodes 
        """
        comment_nodes = doc.xpath('//comment()')
        for c in comment_nodes:
            escaped = etree.Element("{%s}comment" % nsmap["xsl"])
            escaped.text = c.text 
            self.replace_element(c,escaped)
    

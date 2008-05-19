from lxml import etree
from deliverance import xinclude
import copy 
import re
from deliverance import utils
from deliverance.utils import RuleSyntaxError
from deliverance.utils import RendererBase
from deliverance.utils import rule_tostring


xslt_wrapper_skel = """
<xsl:transform version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">

  <!-- empty templates for moved or dropped nodes are inserted here --> 

  <!-- this is the top level rule --> 
  <xsl:template match="/" priority="2">
    <!-- theme goes here --> 
  </xsl:template>

  <!-- this copies whatever the current node is when apply-templates is called in normal mode --> 
  <xsl:template match="node()|@*">
    <xsl:copy>
      <xsl:apply-templates select="node()|@*" />
    </xsl:copy>
  </xsl:template>

  <!-- this copies whatever the current node is when apply-templates is called in move mode -->
  <xsl:template match="node()|@*" mode="move" >
    <xsl:copy>
      <xsl:apply-templates select="node()|@*" />
    </xsl:copy>
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
        import warnings
        warnings.warn("The XSLT renderer is deprecated; please use deliverance.interpreter.Renderer instead.  The XSLT renderer may produce different results than the Python renderer", DeprecationWarning)
        theme_copy = copy.deepcopy(theme)
        self.rules = rule
        self.rules_uri = rule_uri

        self.fixup_links(theme_copy, theme_uri)
        self.xsl_escape_comments(theme_copy)
        self.avt_escape(theme_copy)

        self.resolve_uri = reference_resolver
        if self.resolve_uri:
            xinclude.include(self.rules, self.rules_uri, loader=self.resolve_uri)


        debug = self.rules.get("debug", None)
        if debug and debug.lower() == "true":
            self.debug = True
        else:
            self.debug = False

        self.transform = None
        
        self.xslt_wrapper = etree.XML(xslt_wrapper_skel)
        self.apply_rules(self.rules,theme_copy)
    

        insertion_point = self.xslt_wrapper.xpath("//xsl:transform/xsl:template[@match='/']",
                                             nsmap)[0]
        insertion_point.append(theme_copy)

        self.transform = etree.XSLT(self.xslt_wrapper)
    
        

    def render(self, content):
        """
        content: an lxml etree structure representing the content to render 
        returns an lxml etree structure representing the result of the 
                transformation represented by this class performed on the 
                given content. 
        """
        if self.shouldnt_theme(content):
            return copy.deepcopy(content)

        #print "TRANSFORM: %s" % etree.tostring(self.xslt_wrapper)
        if content is not None:
            content = self.aggregate(self.resolve_uri, self.rules, content)
            return self.transform(content).getroot()
        else:
            return self.transform(etree.Element("dummy")).getroot()


    def apply_rules(self, rules, theme):
        """
        prepares an xslt transforms which accpet a content document. 
        The transforms represent the application of 
        the rules given in the context of the theme given. 
        """
        for rule in rules:
            self.apply_rule(rule, theme)


    def apply_rule(self, rule, theme):
        """
        dispatch to proper rule handling function for 
        the rule given. 
        """
        #print "APPLY: %s " % etree.tostring(rule) 
        self.check_move(rule,theme)
        
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

        copier = self.make_copy_node(rule)
        
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

        copier = self.make_copy_node(rule)
        
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

        copier = self.make_copy_node(rule, nocontent_fallback=[copy.deepcopy(theme_el)])

        self.debug_replace(theme_el,copier,rule)


    def apply_copy(self, rule, theme):
        """
        prepare transform elements for "copy" rule 
        """

        theme_el = self.get_theme_el(rule, theme)
        if theme_el is None:
            return 

        # add an element that produces an error in the theme if 
        # no content is matched 
        self.add_conditional_missing_content_error(theme,rule)

        theme_copy = copy.deepcopy(theme_el)
        fallback = theme_copy.xpath("text()|child::node()")
        theme_el.text = None
        del(theme_el[:])        
        copier = self.make_copy_node(rule,nocontent_fallback=fallback)
        self.debug_append(theme_el,copier,rule)
        

   
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
                                self.get_content_xpath(rule))
                conditional.append(copy.deepcopy(el))
                self.replace_element(el,conditional)
 
        copier = self.make_copy_node(rule)
           
        self.debug_append(theme_el, copier, rule)


    def apply_drop(self, rule, theme):
        """
        prepare transform elements for "drop" rule 
        """
        if self.RULE_THEME_KEY in rule.attrib:
            if len(theme.xpath(rule.attrib[self.RULE_THEME_KEY])) == 0:
                if rule.get(self.NOTHEME_KEY) == self.IGNORE_KEYWORD:
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
            empty_template = etree.Element("{%s}template" % nsmap["xsl"])
            empty_template.set("priority","1")
            empty_template.set("match",self.get_content_xpath(rule))

            move_empty_template = copy.deepcopy(empty_template)
            move_empty_template.set("mode","move")
            
            self.xslt_wrapper[0:0] = [empty_template,move_empty_template]
            
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
        if rule.get(self.NOCONTENT_KEY) == self.IGNORE_KEYWORD:
            return

        err = self.format_error("no content matched", rule)
        if err is not None:
            # if the content was possibly moved, check for a marker instead of the content 
            check_xpath = self.get_content_xpath(rule)
                
            conditional = etree.Element("{%s}if" % nsmap["xsl"])
            conditional.set("test", "count(%s)=0" % check_xpath)
            conditional.append(err)
            self.add_to_body_start(theme, conditional)
        

    def make_when_otherwise(self, test, when_els, otherwise_els):
        """
        makes a conditional xlst node. when placed into a document, 
        if the xslt expression represented by the string test evaluates 
        to true, when_els are produced, if false, otherwise_els are produced
        """

        choose = etree.Element("{%s}choose" % nsmap["xsl"])
        when = etree.Element("{%s}when" % nsmap["xsl"])
        when.set("test", test)
        otherwise = etree.Element("{%s}otherwise" % nsmap["xsl"])

        self.append_many(when,when_els)
        self.append_many(otherwise,otherwise_els)
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
        comment_before.text = "Deliverance: applying rule %s" % rule_tostring(rule)
        comment_after = etree.Element("{%s}comment" % nsmap["xsl"])
        comment_after.text = "Deliverance: done applying rule %s" % rule_tostring(rule)
        return comment_before, comment_after


    def make_copy_node(self,rule, nocontent_fallback=None):

        apply = etree.Element("{%s}apply-templates" % nsmap["xsl"])
        apply.set("select",self.get_content_xpath(rule))
                  
        if rule.get(self.RULE_MOVE_KEY,None) is not None:
            apply.set("mode","move")
            # in the normal mode it is ignored 
            empty_template = etree.Element("{%s}template" % nsmap["xsl"])
            empty_template.set("priority","1")
            empty_template.set("match",self.get_content_xpath(rule))

            self.xslt_wrapper[0:0] = [empty_template]
            
        if nocontent_fallback is None:
            return apply 
        else:
            return self.make_when_otherwise("count(%s)=0" % 
                                            self.get_content_xpath(rule), 
                                            nocontent_fallback, 
                                            [apply])            

                       
    def check_move(self,rule,theme):
        if rule.get(self.RULE_MOVE_KEY, None) is None:
            return

        if rule.tag == self.SUBRULES_TAG or rule.tag == self.DROP_RULE_TAG: 
            e = self.format_error("rule does not support the move attribute", rule)
            self.add_to_body_start(theme, e)
            return

        theme_els = theme.xpath(rule.get(self.RULE_THEME_KEY))
        if theme_els is None or len(theme_els) == 0:
            if rule.get(self.NOTHEME_KEY,None) == self.IGNORE_KEYWORD:
                del(rule.attrib[self.RULE_MOVE_KEY]) # just process it normally
            return

    def avt_escape(self,elt): 
        """
        replaces all instances of { or } with {{ and }} to avoid 
        being interpreted as an Attribute Value Template by XSLT 
        """
        
        for (k,v) in elt.attrib.items():
            escaped = v.replace('{','{{')
            escaped = escaped.replace('}','}}')
            elt.attrib[k] = escaped 

        for child in elt: 
            self.avt_escape(child)

        

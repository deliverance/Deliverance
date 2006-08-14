import os
from lxml import etree
from time import time
from lxml.etree import Namespace, ElementBase


nsmap = {
    "dv": "http://www.plone.org/deliverance",
    "html": "http://www.w3.org/1999/xhtml",
    "xsl": "http://www.w3.org/1999/XSL/Transform",
    "at": "http://plone.org/archetypes",
    }

class AppMap:

    def __init__(self, layout_dir):
        
        # Open the appmap file, make a tree, and process XIncludes
        self.module_dir = os.path.dirname(os.path.abspath(__file__))
        self.layout_dir = os.path.join(self.module_dir, layout_dir)
        layoutsfn = os.path.join(self.layout_dir, "appmap.xml")
        self.tree = etree.ElementTree(file=layoutsfn)
        self.tree.xinclude()

        # Make a themeprocessor to style all outgoing pages.  Note that the 
        # .processor attribute comes from an lxml namespace binding, meaning it is 
        # defined via a custom Python class defined below (class LayoutElement)
        root = self.tree.getroot()
        layout = root.xpath("dv:layouts/dv:layout", nsmap)[0]
        self.themeprocessor = make_processor(layout)


    def publish(self, xmlstring):
        """Given a string of XML, theme it"""
        
        resource = etree.XML(xmlstring)
        response = str(self.themeprocessor(resource))

        return response

# The following are extensions based on lxml namespace extensions.  It 
# adds Python behavior to XML nodes.

class DVRuleBase(ElementBase):

    def getThemeNode(self):
        return getThemeNode(self)

def getThemeNode(el):
    """Get a node in the theme doc"""

    # Current node is a rule, get xpath from the @theme attr
    themedoc = el.xpath("../../dv:theme", nsmap)[0][0]
    xpath = el.get("theme")
    try:
        themenode = themedoc.xpath(xpath, nsmap)[0]
    except IndexError:
        msg = "Themedoc has no node at: %s" % xpath
        print msg
        themenode = None

    return themenode


class LayoutElement(ElementBase):

    def processor(self):
        return make_processor(self)
    
    processor = property(processor)

def make_processor(el):
    """Make XSLT processor by changing theme based on rules"""

    # Apply all the rules
    for rule in el.xpath("./dv:rules/*", nsmap):
        apply_rules(rule)

    # Merge applied rules into compilerdoc
    compilerroot = el.xpath("../dv:compiler/xsl:stylesheet", nsmap)[0]
    themeroot = el.xpath("dv:theme/html:html", nsmap)[0]
    target = compilerroot.xpath("xsl:template[@match='/']", nsmap)[0]
    target.append(themeroot)

    #print etree.tostring(compilerroot)

    return etree.XSLT(compilerroot)
        

class RuleReplaceElement(DVRuleBase):

    def apply(self):
        return apply_rules(self)

def apply_rules(el):
    # TODO: Someething here
    themenode = getThemeNode(el)
    if themenode is None:
        return
    del(themenode[:])
    themenode.text = None
    xslvalueof = etree.SubElement(themenode,
                                  "{%s}value-of" % nsmap["xsl"])
    xslvalueof.set("select", el.get("content"))


class RuleCopyElement(DVRuleBase):

    def apply(self):
        themenode = self.getThemeNode()
        if themenode is None:
            return
        del(themenode[:])
        themenode.text = None
        xslvalueof = etree.SubElement(themenode,
                                      "{%s}apply-templates" % nsmap["xsl"])
        xslvalueof.set("select", self.get("content"))


class RuleAppendElement(DVRuleBase):

    def apply(self):
        themenode = self.getThemeNode()
        if themenode is None:
            return
        xslvalueof = etree.SubElement(themenode,
                                      "{%s}apply-templates" % nsmap["xsl"])
        xslvalueof.set("select", self.get("content"))


# Bind Python classes for lxml namespace support
namespace = Namespace(nsmap['dv'])
namespace['layout'] = LayoutElement
namespace['replace'] = RuleReplaceElement
namespace['copy'] = RuleCopyElement
namespace['append'] = RuleAppendElement
    

def timeit(xmlstring):
    appmap = AppMap()
    start = time()
    iters = 50
    for i in range(iters):
        result = appmap.publish(xmlstring)
    print "*** Average time:", (time() - start) / iters, " ***\n"
    print result[0:2000]
    
def main():
    xmlstring = open("content/index.html").read()
    timeit(xmlstring)
    
if __name__ == "__main__":
    main()

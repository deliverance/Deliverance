"""
Generating XSLT processors from HTML themes and rule files.

A Deliverance thememap takes an XML configuration file (theme map) 
and 'compiles' one or more themes.  The configuration file specifies 
each theme, the file with the layout for that theme, the rule file 
governing how content will be merged into that theme, and the 
'compiler' used to build the theme.

The result is a mapping of theme ids to XSLT processors.  The 
XSLT processors contain no lxml-specific instructions.  They 
could be printed to a file and applied via xsltproc or included 
in browser-side transformations.

The rules in the rulefile are paired with lxml namespace bindings. 
Each rule thus has a Python class that implements the rule 
behavior.  This allows the rules to be extended to cover custom 
uses.

"""
import os, copy
from lxml import etree
from time import time
from lxml.etree import Namespace, ElementBase

nsmap = {
    "dv": "http://www.plone.org/deliverance",
    "html": "http://www.w3.org/1999/xhtml",
    "xsl": "http://www.w3.org/1999/XSL/Transform",
    }
xmlbase = "{http://www.w3.org/XML/1998/namespace}base"

class ThemeMap:

    def __init__(self, thememapfn=None):
        
        # Open the themes config file, make a tree, and process XIncludes
        self.module_dir = os.path.dirname(os.path.abspath(__file__))
        if not thememapfn:
            # Use a default thememap XML file
            thememapfn = os.path.join(self.module_dir, "etc/thememap.xml")
        self.tree = etree.ElementTree(file=thememapfn)
        self.tree.xinclude()

        # Make a mapping for each theme, allowing us to choose from more 
        # than one theme.  The key is the id attribute for the theme and 
        # the value is the generated XSLT processor, made from the rule 
        # file for that theme.
        self.themes = {}
        themenodes = self.tree.xpath("dv:theme", nsmap)
        for themenode in themenodes:
            themeid = themenode.get("themeid")
            themeprocessor = self.makeProcessor(themenode)
            self.themes[themeid] = themeprocessor
        self.defaulttheme = themenodes[0].get("themeid")


    def makeProcessor(self, themenode):
        """Make XSLT processor by changing theme based on rules"""
        
        # First make a new <processordoc> that will hold the markup
        # for the XSLT built from the HTML theme, the rules, and 
        # the generator XSLT.  We can then visually inspect the 
        # results of theme generation.
        processordoc = etree.SubElement(themenode, 
                                        "{%s}processordoc" % nsmap['dv'])

        # Second, make a copy of the generator XSLT and insert it into 
        # the processordoc node.
        generatorroot = themenode.xpath("dv:generator/xsl:stylesheet", 
                                        nsmap)[0]
        processorroot = copy.deepcopy(generatorroot)
        processordoc.append(processorroot)
        
        # Third, take the HTML from the layout and shove it into the 
        # XSLT generator (and remove stray xml:base attribute)
        themeroot = themenode.xpath("dv:layout/html:html", nsmap)[0]
        del themeroot.attrib[xmlbase]
        target = processorroot.xpath("xsl:template[@match='/']", nsmap)[0]
        target.append(copy.deepcopy(themeroot))

        # Now apply the rules by calling the "apply" method that 
        # was bound via lxml's namespace bindings (defined below)
        for rule in themenode.xpath("dv:rules/*", nsmap):
            rule.apply()

        # Create and return an XSLT processor
        return etree.XSLT(processorroot)


    def applyTheme(self, xmlstring, themeid="default"):
        """Given a string of XML, theme it"""

        if themeid=="default":
            themeid = self.defaulttheme
        resource = etree.XML(xmlstring)
        themeprocessor = self.themes[themeid]
        response = str(themeprocessor(resource))

        return response


    def __str__(self):
        return etree.tostring(self.tree)


# The following are extensions based on lxml namespace extensions.  It 
# adds Python behavior to XML nodes.  Based on this, you can customize 
# the ruleset for controlling the merge.

class DVRuleBase(ElementBase):

    def getThemeNode(self):
        """Get a node in the theme doc"""

        # We want to modify the theme HTML that was copied into 
        # the <processordoc>
        proot = self.xpath("../../dv:processordoc", nsmap)[0]
        phtmlroot = proot.xpath("xsl:stylesheet/xsl:template/html:html", 
                                nsmap)[0]

        # Starting at the processor's html root (phtmlroot), grab
        # the theme node pointed to by this rule's "theme" attribute.
        themexpath = self.get("theme")
        try:
            themenode = phtmlroot.xpath(themexpath, nsmap)[0]
            #print "Found themenode", themenode, "for rule", themexpath
        except IndexError:
            msg = "Themedoc has no node at: %s" % themexpath
            print msg
            themenode = None

        return themenode


class RuleReplaceElement(DVRuleBase):

    def apply(self):
        themenode = self.getThemeNode()
        if themenode is None:
            return
        del(themenode[:])
        themenode.text = None
        xslvalueof = etree.SubElement(themenode,
                                      "{%s}value-of" % nsmap["xsl"])
        xslvalueof.set("select", self.get("content"))


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


# Bind Python classes for lxml namespace support.  This implements 
# the rules in the rulefile.
namespace = Namespace(nsmap['dv'])
namespace['replace'] = RuleReplaceElement
namespace['copy'] = RuleCopyElement
namespace['append'] = RuleAppendElement
    

def main():
    xmlstring = open("content/intro.html").read()
    thememap = ThemeMap()
    start = time()
    iters = 50
    for i in range(iters):
        result = thememap.applyTheme(xmlstring, "simple")
    print result[0:2000]
    print "*** Average time:", (time() - start) / iters, " ***\n"
    return thememap
    
    
if __name__ == "__main__":
    thememap = main()
    print thememap

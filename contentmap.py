"""
contentmap - Manage an in-memory map of content and renderers.

This module reads a map of resources in an XML file and provides 
several services:

  o Pre-calculate certain statistics
  
  o Retrieve a resource that is published online
  
  o Render that resource to XHTML
"""

import os
from lxml import etree

class ContentMap:

    def __init__(self, contentmapfn=None):
        
        # Open the content file, make a tree, and process XIncludes
        module_dir = os.path.dirname(os.path.abspath(__file__))        
        if not contentmapfn:
            layoutsfn = os.path.join(module_dir, "samplemap.xml")
        self.tree = etree.ElementTree(file=layoutsfn)
        self.tree.xinclude()

        # Published resources that come from the appmap content (vs. an 
        # html file on disk) need to get rendered to XHTML first.  The 
        # rendererprocessor XSLT does this.
        rendererfn = os.path.join(module_dir, "contentrenderer.xsl")
        rendererdoc = etree.ElementTree(file=rendererfn)
        self.rendererprocessor = etree.XSLT(rendererdoc)


    def publish(self, path_info):
        """Find a resource, generate markup, and apply theme"""

        # Pass path_info in as xslt parameter to XSLT that renders nodes 
        # in the appmap
        response = self.rendererprocessor(self.tree,
                                        pathinfo="'%s'" % path_info)

        return str(response)

def main():
    contentmap = ContentMap()
    response = contentmap.publish("providers.joelburton")
    print response

if __name__ == "__main__":
    main()

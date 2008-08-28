from lxml import etree
import re
import threading

html_xsl = """
<xsl:transform xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
  <xsl:output method="html" encoding="UTF-8" /> 
  <xsl:template match="/">
    <xsl:copy-of select="."/>
  </xsl:template>
</xsl:transform>
"""

# TODO: this should be xsl for real formatting 
pretty_html_xsl = html_xsl

pretty_html_transforms = threading.local()
html_transforms = threading.local()

def get_pretty_html_transform():
    try:
        return pretty_html_transforms.transform
    except AttributeError:
        t = pretty_html_transforms.transform = etree.XSLT(etree.XML(pretty_html_xsl))
        return t

def get_html_transform():
    try:
        return html_transforms.transform
    except AttributeError:
        t = html_transforms.transform = etree.XSLT(etree.XML(html_xsl))
        return t

def tostring(doc, pretty = False, doctype_pair=None):
    """
    return HTML string representation of the document given 
 
    note: this will create a meta http-equiv="Content" tag in the head
    and may replace any that are present 
    """

    if pretty:
        doc = str(get_pretty_html_transform()(doc))
    else:
        doc = str(get_html_transform()(doc))

    if doctype_pair: 
        doc = """<!DOCTYPE html PUBLIC "%s" "%s">\n%s""" % (doctype_pair[0], doctype_pair[1], doc) 

    return doc

                  



#HTTP_EQUIV_MATCHER_PAT = re.compile(r"\<\s*meta\s+([^\>])*http-equiv\s*=\s*(\'|\")\s*content-type\s*(\'|\")([^\>])*charset\s*=\s*(?P<charset>[\w-]+)([^\>])*\>",re.I|re.M) 
#OTHER_HTTP_EQUIV_MATCHER_PAT = re.compile(r"\<\s*meta\s+([^\>])*charset\s*=\s*(?P<charset>[\w-]+)([^\>])*http-equiv\s*=\s*(\'|\")\s*content-type\s*(\'|\")([^\>])*\>",re.I|re.M) 
def decodeAndParseHTML(text):
    """
    if an html meta tag specifying a charset can be matched, 
    decode the text to a python unicode string before parsing

    XXX - this is disabled and in camelCase for no good reason 
    """
#    m = HTTP_EQUIV_MATCHER_PAT.search(text)
#    if not m:
#        m = OTHER_HTTP_EQUIV_MATCHER_PAT.search(text)
#
#    if m:
#        charset = m.group('charset')
#        text = text.decode(charset)

    content = etree.HTML(text)
    assert content is not None
    return content
    

        

    

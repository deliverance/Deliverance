from lxml import etree
import re

html_xsl = """
<xsl:transform xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
  <xsl:output method="html" encoding="UTF-8" />
  <xsl:template match="/">
    <xsl:copy-of select="."/>
  </xsl:template>
</xsl:transform>
"""

# TODO: this should do real formatting 
pretty_html_xsl = """
<xsl:transform xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
  <xsl:output method="html" indent="yes" />
  <xsl:template match="/">
    <xsl:copy-of select="."/>
  </xsl:template>
</xsl:transform>
"""

html_transform = etree.XSLT(etree.XML(html_xsl))
pretty_html_transform = etree.XSLT(etree.XML(pretty_html_xsl))


#
# creates an HTML string representation of the document given 
# 
# note: this will create a meta http-equiv="Content" tag in the head
# and may replace any that are present 
# 
def tostring(doc,pretty = False):
    if pretty:
        return str(pretty_html_transform(doc))
    else:
        return str(html_transform(doc))
                  



HTTP_EQUIV_MATCHER_PAT = re.compile(r"\<\s*meta\s+([^\>])*http-equiv\s*=\s*(\'|\")\s*content-type\s*(\'|\")([^\>])*charset\s*=\s*(?P<charset>[\w-]+)([^\>])*\>",re.I|re.M) 
OTHER_HTTP_EQUIV_MATCHER_PAT = re.compile(r"\<\s*meta\s+([^\>])*charset\s*=\s*(?P<charset>[\w-]+)([^\>])*http-equiv\s*=\s*(\'|\")\s*content-type\s*(\'|\")([^\>])*\>",re.I|re.M) 
def decodeAndParseHTML(text):
    """
    if an html meta tag specifying a charset can be matched, 
    decode the text to a python unicode string before parsing
    """
    m = HTTP_EQUIV_MATCHER_PAT.search(text)
    if not m:
        m = OTHER_HTTP_EQUIV_MATCHER_PAT.search(text)

    if m:
        charset = m.group('charset')
#        text = text.decode(charset)

    content = etree.HTML(text)
    assert content is not None
    return content
    

        

    

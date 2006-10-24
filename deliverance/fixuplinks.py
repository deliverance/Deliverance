from htmlserialize import decodeAndParseHTML, tostring
import re

def fixup_text_links(doc, link_repl_func, remove_base_tags=True):
    """
    fixup_links(), but work on text and returns text
    """
    doc = decodeAndParseHTML(doc)
    fixup_links(doc, link_repl_func, remove_base_tags=remove_base_tags)
    return tostring(doc)

def fixup_links(doc, link_repl_func,
                remove_base_tags=True):
    """
    Takes a given document (already parsed by lxml) and modifies it
    in-place.  Every link is passed through link_repl_func, and the
    output of that function replaces the link.
    """
    if remove_base_tags:
        remove_base_tags_from_document(doc)

    for attrib in 'href', 'src':
        els = doc.xpath('//*[@%s]' % attrib)
        for el in els:
            el.attrib[attrib] = link_repl_func(el.attrib[attrib])

    fixup_css_links(doc, link_repl_func)

def remove_base_tags_from_document(doc):
    basetags = doc.xpath('//base[@href]')
    for b in basetags:
        b.getparent().remove(b)
    
CSS_URL_PAT = re.compile(r'url\((.*?)\)',re.I)
def fixup_css_links(doc, link_repl_func):
    """ 
    prepends url(...) in css style elements to be 
    absolute links based on base_uri
    """
    def absuri(matchobj):
        return 'url(%s)' % link_repl_func(matchobj.group(1))
    els = doc.xpath('//head/style')
    for el in els:
        if el.text:
            el.text = re.sub(self.CSS_URL_PAT,absuri,el.text)


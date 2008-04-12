"""
utilities for manipulating html links 
"""


from deliverance.htmlserialize import decodeAndParseHTML, tostring
from deliverance.utils import get_serializer
import urlparse
import re

def fixup_text_links(environ, doc, link_repl_func, remove_base_tags=True):
    """
    fixup_links(), but work on text and returns text
    """
    doc = decodeAndParseHTML(doc)
    fixup_links(doc, link_repl_func, remove_base_tags=remove_base_tags)
    serializer = get_serializer(environ, tostring)
    return serializer(environ, doc)

def fixup_links(doc, link_repl_func,
                remove_base_tags=True):
    """
    Takes a given document (already parsed by lxml) and modifies it
    in-place.  Every link is passed through link_repl_func, and the
    output of that function replaces the link.
    """
    if remove_base_tags:
        resolve_base_tags_in_document(doc)

    for attrib in 'href', 'src':
        els = doc.xpath('//*[@%s]' % attrib)
        for el in els:
            el.attrib[attrib] = link_repl_func(el.attrib[attrib])

    fixup_css_links(doc, link_repl_func)

def resolve_base_tags_in_document(doc):
    """
    removes all html <base href=""> tags 
    from the document given. 
    """
    base_href = None
    basetags = doc.xpath('//base[@href]')
    for b in basetags:
        base_href = b.attrib['href']
        b.getparent().remove(b)
    if base_href is None:
        return
    # Now that we have a base_href (blech) we have to fix up all the
    # links in the document with this new information.
    def link_repl(href):
        return urlparse.urljoin(base_href, href)
    fixup_links(doc, link_repl, remove_base_tags=False)
    
CSS_URL_PAT = re.compile(r'url\((.*?)\)', re.I)
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
            el.text = re.sub(CSS_URL_PAT,absuri,el.text)


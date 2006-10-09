from lxml import etree
import re
import urlparse

class RuleSyntaxError(Exception):
    """
    Raised when an invalid or unknown rule is encountered by a renderer 
    during rule processing 
    """


class RendererBase(object):
    """
    base class for deliverance renderers. 
    subclasses should implement: 

    render(self,content) 

    which should accept an lxml.etree structure and produce 
    an lxml.etree structure representing the content having been 'themed' 
    with this renderer's theme according to its rules. 
    """

    APPEND_RULE_TAG            = "{http://www.plone.org/deliverance}append"
    PREPEND_RULE_TAG           = "{http://www.plone.org/deliverance}prepend"
    REPLACE_RULE_TAG           = "{http://www.plone.org/deliverance}replace"
    COPY_RULE_TAG              = "{http://www.plone.org/deliverance}copy"
    APPEND_OR_REPLACE_RULE_TAG = "{http://www.plone.org/deliverance}append-or-replace"
    SUBRULES_TAG               = "{http://www.plone.org/deliverance}rules"

    RULE_CONTENT_KEY = "content"
    RULE_THEME_KEY   = "theme" 

    def get_theme_el(self,rule,theme):
        theme_els = theme.xpath(rule.attrib[self.RULE_THEME_KEY])
        if len(theme_els)== 0:
            e = self.format_error("no element found in theme", rule)
            self.add_to_body_start(theme, e)
            return None
        elif len(theme_els)> 1:
            e = self.format_error("multiple elements found in theme", rule)
            theme_els[0].append(e)
            return None
        return theme_els[0]


    def format_error(self, message, rule, elts=None):
        """
        Returns a node containing the error message;
        Checks the onerror attribute of the rule element to see if errors should
        be ignored in which case returns None
        """

        if rule.attrib.get('onerror', None) == 'ignore':
            return None

        d = etree.Element('div')
        d.attrib['class'] = 'deliverance-error'
        d.text = 'Deliverance error: %s' % message
        br = etree.Element('br')
        br.tail = 'rule: %s' % etree.tostring(rule)
        d.append(br)
        if elts:
            d.extend(elts)
        return d


    TAG_MATCHER = re.compile(r'^\.?/?/?(.*?/)*(?P<tag>[^*^(^)^:^[^.^/]+?)(\[.*\])*$',re.I)
    def get_tag_from_xpath(self,xpath):
        match = self.TAG_MATCHER.match(xpath)
        if match:
            return match.group('tag')  
        else:
            return None


    def add_to_body_start(self,theme, el):
        body = theme.find('body')
        if body is None:
            body = theme[0]
        body[:0] = [el]

    def replace_element(self,replace, new_el):
        parent = replace.getparent()
        for i in range(len(parent)):
            if parent[i] == replace:
                new_el.tail = replace.tail 
                parent[i] = new_el
                break

    def mark_bad_elements(self,els):
        for el in els:
            if 'class' in el.attrib:
                el.attrib['class'] += ' deliverance-bad-element'
            else:
                el.attrib['class'] = 'deliverance-bad-element'


    def fixup_links(self, doc, uri):
        """ resolve all links in the ``doc`` element to be absolute; the links
        should be considered relative to ``uri``
        """        
        base_uri = uri 
        basetags = doc.xpath('//base[@href]')
        if (len(basetags)):
            base_uri = basetags[0].attrib['href']

            for b in basetags:
                b.getparent().remove(b)

        elts = doc.xpath('//*[@href]')
        self.fixup_link_attrs(elts, base_uri, 'href')

        elts = doc.xpath('//*[@src]')
        self.fixup_link_attrs(elts, base_uri, 'src')

        elts = doc.xpath('//head/style')
        self.fixup_css_links(elts, base_uri)

        return doc


    def fixup_link_attrs(self, elts, base_uri, attr):
        """ makes all attr values in elts to be absolute uris based on base_uri """
        for el in elts:
            el.attrib[attr] = urlparse.urljoin(base_uri, el.attrib[attr])


    CSS_URL_PAT = re.compile(r'url\((.*?)\)',re.I)
    def fixup_css_links(self, elts, base_uri):
        """ fixes @import uris in css style elements to be 
        absolute links based on base_uri
        """

        def absuri(matchobj): 
            return 'url(' + urlparse.urljoin(base_uri,matchobj.group(1)) + ')'

        for el in elts:
            if el.text:
                el.text = re.sub(self.CSS_URL_PAT,absuri,el.text)

    def remove_http_equiv_metas(self,doc):
        if not doc:
            return 

        metas = doc.xpath("//meta[translate(@http-equiv,'contenyp','CONTENYP') = 'CONTENT-TYPE']")
        for elt in metas:
            if elt.tail:
                attach_text_to_previous(self,elt,elt.tail)
            elt.getparent().remove(elt)


    def attach_text_to_previous(self,el,text):
        if text is None:
            return 

        el_i = el.getparent().index(el)
        if el_i > 0:
            sib_el = el.getparent()[el_i - 1]
            if sib_el.tail:
                sib_el.tail += text 
            else:
                sib_el.tail = text
        else: 
            if el.getparent().text:
                el.getparent().text += text 
            else:
                el.getparent().text = text

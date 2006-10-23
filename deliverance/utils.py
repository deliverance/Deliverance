from lxml import etree
import re
import urlparse
import htmlserialize

# Test if the libxml2 fix is in place
html = etree.HTML('<html><head><script>some text</script></head></html>')
if html[0][0].text != 'some text':
    import warnings
    warnings.warn(
        'Deliverance requires the CVS HEAD version of libxml2')

class DeliveranceError(Exception):
    """
    General Deliverance Error.
    """    

class RuleSyntaxError(DeliveranceError):
    """
    Raised when an invalid or unknown rule is encountered by a renderer 
    during rule processing 
    """

DELIVERANCE_ERROR_PAGE = """
<html>
<head>
  <title>Deliverance Error</title>
</head>
<body>
  <H3>Deliverance Error</H3>
  <p>An error occurred processing the request<BR>
  <pre>
    %s
  </pre>
  <p>Stack Trace:
  <pre>
    %s
  </pre>
</body>
</html>
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

    NOCONTENT_KEY = "nocontent"

    def get_theme_el(self,rule,theme):
        theme_els = theme.xpath(rule.attrib[self.RULE_THEME_KEY])
        if len(theme_els)== 0:
            e = self.format_error("no element found in theme", rule)
            self.add_to_body_start(theme, e)
            return None
        elif len(theme_els)> 1:
            e = self.format_error("multiple elements found in theme", rule, theme_els)
            self.add_to_body_start(theme, e)
            return None
        return theme_els[0]


    def format_error(self, message, rule, elts=None):
        """
        Returns a node containing the error message;
        If the onerror attribute of the rule element is set to ignore,
        returns None
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
            d.append(etree.Element('br'))
            textArea = etree.Element('textarea')
            textArea.attrib['rows'] = '24'
            textArea.attrib['cols'] = '80'
            textArea.attrib['readonly'] = 'readonly'
            textArea.text = ''
            for el in elts:
                textArea.text += htmlserialize.tostring(el)
            d.append(textArea)
        return d


    TAG_MATCHER = re.compile(r'^\.?/?/?(.*?/)*(?P<tag>[^*^(^)^:^[^.^/]+?)(\[.*\])*$',re.I)
    def get_tag_from_xpath(self,xpath):
        """
        attemtps to extract the tag type that an xpath expression selects (if any)
        """
        match = self.TAG_MATCHER.match(xpath)
        if match:
            return match.group('tag')  
        else:
            return None


    def add_to_body_start(self,doc,el):
        """
        inserts the element el into the beginning of body 
        element of the document given        
        """
        if not el:
            return
        body = doc.find('body')
        if body is None:
            body = doc[0]
        body[:0] = [el]

    def replace_element(self,old_el, new_el):
        """
        replaces old_el with new_el in the parent 
        element of old_el. The tail of 
        new_el is replaced by the tail of old_el 
        """
        new_el.tail = old_el.tail
        parent = old_el.getparent()
        parent[parent.index(old_el)] = new_el



    def fixup_links(self, doc, uri):
        """ 
        replaces relative urls found in the document given 
        with absolute urls by prepending the uri given. 
        <base href> tags are removed from the document. 

        Affects urls in href attributes, src attributes and 
        css of the form url(...) in style elements 
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
        """
        prepends base_uri onto the attribute given by attr for 
        all elements given in elts 
        """
        for el in elts:
            el.attrib[attr] = urlparse.urljoin(base_uri, el.attrib[attr])


    CSS_URL_PAT = re.compile(r'url\((.*?)\)',re.I)
    def fixup_css_links(self, elts, base_uri):
        """ 
        prepends url(...) in css style elements to be 
        absolute links based on base_uri
        """

        def absuri(matchobj): 
            return 'url(' + urlparse.urljoin(base_uri,matchobj.group(1)) + ')'

        for el in elts:
            if el.text:
                el.text = re.sub(self.CSS_URL_PAT,absuri,el.text)


    def attach_text_to_previous(self,el,text):
        """
        attaches the text given to the nearest previous node to el, 
        ie its preceding sibling or parent         
        """
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

   

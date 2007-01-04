from lxml import etree
import re
import urlparse
import copy
from deliverance import htmlserialize
import sys

# Test if the libxml2 fix is in place
html = etree.HTML('<html><head><script>some text</script></head></html>')
if html[0][0].text != 'some text':
    import warnings
    warnings.warn(
        'Deliverance requires a newer version of libxml2 (1.1.18 or later)')

# And another fix:
html_comment = etree.Comment('test comment')
if copy.deepcopy(html_comment) is None:
    import warnings
    warnings.warn(
        'Deliverance requires a newer version of lxml (1.2 or later)')

if sys.version_info <= (2, 4, 1):
    # There are reported threading issues for this version
    import warnings
    warnings.warn(
        'lxml has threading problems for Python 2.4.1 and earlier')

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
    DROP_RULE_TAG              = "{http://www.plone.org/deliverance}drop"

    RULE_CONTENT_KEY = "content"
    RULE_THEME_KEY   = "theme" 
    RULE_MOVE_KEY = "move"
    RULE_HREF_KEY = "href"

    NOCONTENT_KEY = "nocontent"
    NOTHEME_KEY = "notheme"

    IGNORE_KEYWORD = "ignore"

    REQUEST_CONTENT = "deliverance:request-content"

    def get_theme_el(self,rule,theme):
        """
        get the element referred to by the "theme" attribute of the 
        rule given in the theme document given. theme and rule 
        should be lxml etree structures. 
        """
        theme_els = theme.xpath(rule.get(self.RULE_THEME_KEY))
        if len(theme_els)== 0:
            if rule.get(self.NOTHEME_KEY) != self.IGNORE_KEYWORD: 
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

        if rule.get('onerror',None) == self.IGNORE_KEYWORD:
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
                textArea.text += etree.tostring(el)
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
        if basetags:
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

    def separate_drop_rules(self, rules):
        """
        separates out drop rules from a list of rules, returns two 
        lists. 

        first the list of all drop rules, second all other rules 
        order is preserved. 
        """
        regular_rules = []
        drop_rules = []
        for rule in rules:
            if rule.tag == self.DROP_RULE_TAG:
                drop_rules.append(rule)
            else:
                regular_rules.append(rule)
        return drop_rules, regular_rules

    
    def separate_move_rules(self, rules):
        """
        separates out drop rules from a list of rules, returns two 
        lists. 

        first the list of all drop rules, second all other rules 
        order is preserved. 
        """
        regular_rules = []
        move_rules = []
        for rule in rules:
            if rule.get(self.RULE_MOVE_KEY): 
                move_rules.append(rule)
            else:
                regular_rules.append(rule)
        return move_rules, regular_rules



    CSS_URL_PAT = re.compile(r'url\(\s*[\"\']*(.*?)[\"\']*\s*\)',re.I)
    CSS_IMPORT_PAT = re.compile(r'\@import\s*[\"\'](.*?)[\"\']',re.I)
    def fixup_css_links(self, elts, base_uri):
        """ 
        prepends url(...) in css style elements to be 
        absolute links based on base_uri
        """

        def absuri(matchobj): 
            return 'url(' + urlparse.urljoin(base_uri,matchobj.group(1)) + ')'

        def imp_absuri(matchobj):
            return '@import url(' + urlparse.urljoin(base_uri,matchobj.group(1)) + ')'

        for el in elts:
            if el.text:
                el.text = re.sub(self.CSS_IMPORT_PAT,imp_absuri,el.text)
                el.text = re.sub(self.CSS_URL_PAT,absuri,el.text)


    def append_text(self,parent,text):
        if text is None:
            return
        if len(parent) == 0:
            target = parent
        else:
            target = parent[-1]

        if target.text:
            target.text = target.text + text
        else:
            target.text = text

                

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

    def elements_in(self, els):
        """
        return a list containing elements from els which are not strings 
        """
        return [x for x in els if type(x) is not type(str())]
            


    def strip_tails(self, els):
        """
        for each lxml etree element in the list els, 
        set the tail of the element to None
        """
        for el in els:
            el.tail = None


    def attach_tails(self,els):
        """
        whereever an lxml element in the list is followed by 
        a string, set the tail of the lxml element to that string 
        """
        for index,el in enumerate(els): 
            # if we run into a string after the current element, 
            # attach it to the current element as the tail 
            if (type(el) is not type(str()) and 
                index + 1 < len(els) and 
                type(els[index+1]) is type(str())):
                el.tail = els[index+1]   


    def append_many(self, parent, children):
    
        if children is None or len(children) == 0:
            return
        
        if type(children[0]) is type(str()):
            self.append_text(parent,children[0])            
            children = children[1:]

        non_text_els = self.elements_in(children)
        self.strip_tails(non_text_els)
        self.attach_tails(children)
        
        for el in non_text_els:
            parent.append(el)
            

    def replace_many(self, theme_el, content_els):
        non_text_els = self.elements_in(content_els)
        self.strip_tails(non_text_els)

        # the xpath may return a mixture of strings and elements, handle strings 
                # by attaching them to the proper element 
        if (type(content_els[0]) is type(str())):
            # text must be appended to the tail of the most recent sibling or appended 
            # to the text of the parent of the replaced element
            self.attach_text_to_previous(theme_el, content_els[0])

        if len(non_text_els) == 0:
            self.attach_text_to_previous(theme_el, theme_el.tail)
            theme_el.getparent().remove(theme_el)
            return
        
        self.attach_tails(content_els)

        # this tail, if there is one, should stick around 
        preserve_tail = non_text_els[0].tail 

        #replaces first element
        self.replace_element(theme_el, non_text_els[0])
        temptail = non_text_els[0].tail 
        non_text_els[0].tail = None
        parent = non_text_els[0].getparent()

        # appends the rest of the elements
        i = parent.index(non_text_els[0])
        parent[i+1:i+1] = non_text_els[1:]

        if non_text_els[-1].tail:
            non_text_els[-1].tail += temptail
        else:
            non_text_els[-1].tail = temptail
        
        # tack in any preserved tail we stored above
        if preserve_tail:
            if non_text_els[0].tail:
                non_text_els[0].tail = preserve_tail + non_text_els[0].tail
            else:
                non_text_els[0].tail = preserve_tail

    def aggregate(self, resolve_uri, rules, content): 
        """
        aggregates the requested docuemnt and documents 
        referred to in the "href" attribute of 
        rules into a single document structured like: 

        <content>
          <document content="http://blah.org/foo">...</document>
          <docuemnt content="deliverance:request-content">
            ... 
          </document>
        </content>

        content is an lxml etree structure representing the 
        requested content which appears in the document node
        with content attribute set to the value of REQUEST_CONTENT

        the reference_relover is a function used to get the content of other 
        documents referred to in rules, and is described in the 
        initializer for renderers. 
        """
        root = etree.Element("content")


        if content: 
            request_doc = etree.SubElement(root,"document")
            request_doc.set("content",self.REQUEST_CONTENT)
            request_doc.append(content)

        if resolve_uri is None:
            return root

        aggregated = {}
        for rule in rules: 
            href = rule.get(self.RULE_HREF_KEY,None)
            if href is None or aggregated.has_key(href): 
                continue
            
            doc = resolve_uri(href, parse="html")
            aggregated[href] = True
            if doc is None:
                continue 

            doc_node = etree.SubElement(root,"document")
            doc_node.set("content",href)
            doc_node.append(doc)
        
        return root

    def get_content_xpath(self, rule): 
        """
        gets the xpath to lookup the content referred to by rule 
        in the aggregated content document 
        """
        content_xpath = rule.get(self.RULE_CONTENT_KEY)

        if content_xpath is None:
            return None
        
        if not content_xpath.startswith('/'): 
            content_xpath = '/%s' % content_xpath 

        content_doc = rule.get(self.RULE_HREF_KEY,self.REQUEST_CONTENT)
        new_xpath = "/content/document[@content='%s']%s" % (content_doc,content_xpath)

        return new_xpath



   

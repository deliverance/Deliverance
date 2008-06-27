from deliverance.pagematch import run_matches, Match
from deliverance.rules import Rule, remove_content_attribs, AbortTheme
from lxml.html import tostring, document_fromstring
from lxml.etree import XML
import re
import urlparse
from webob.headerdict import HeaderDict

class RuleSet(object):

    def __init__(self, matchers, rules_by_class, default_theme=None):
        self.matchers = matchers
        self.rules_by_class = rules_by_class
        self.default_theme = default_theme

    def apply_rules(self, req, resp, resource_fetcher, log):
        extra_headers = parse_meta_headers(resp.body)
        if extra_headers:
            response_headers = HeaderDict(resp.headerlist + extra_headers)
        else:
            response_headers = resp.headers
        try:
            classes = run_matches(self.matchers, req, response_headers, log)
        except AbortTheme:
            return resp
        if not classes:
            classes = ['default']
        rules = []
        theme = None
        for class_name in classes:
            ## FIXME: handle case of unknown classes
            ## Or do that during compilation?
            for rule in self.rules_by_class[class_name]:
                if rule not in rules:
                    rules.append(rule)
                    if rule.theme:
                        theme = rule.theme
        if theme is None:
            theme = self.default_theme
            ## FIXME: error if not theme still
        assert theme is not None
        theme_doc = self.get_theme(theme, resource_fetcher, log)
        content_doc = self.parse_document(resp.body, req.url)
        run_standard = True
        for rule in rules:
            rule.apply(content_doc, theme_doc, resource_fetcher, log)
            if rule.suppress_standard:
                run_standard = False
        if run_standard:
            ## FIXME: should it be possible to put the standard rule in the ruleset?
            standard_rule.apply(content_doc, theme_doc, resource_fetcher, log)
        remove_content_attribs(theme_doc)
        ## FIXME: handle caching?
        resp.body = tostring(theme_doc)
        return resp

    def get_theme(self, url, resource_getter, log):
        log.info(self, 'Fetching theme from %s' % url)
        ## FIXME: should do caching
        doc = self.parse_document(resource_getter(url), url)
        doc.make_links_absolute()
        return doc

    def parse_document(self, s, url):
        return document_fromstring(s, base_url=url)

    @classmethod
    def parse_xml(cls, doc, source_location):
        assert doc.tag == 'ruleset'
        matchers = []
        rules = []
        default_theme = None
        for el in doc.iterchildren():
            if el.tag == 'match':
                matcher = Match.parse_xml(el, source_location)
                matchers.append(matcher)
            elif el.tag == 'rule':
                rule = Rule.parse_xml(el, source_location)
                rules.append(rule)
            elif el.tag == 'theme':
                ## FIXME: Add parse error
                default_theme = el.get('href')
            else:
                ## FIXME: better error
                assert 0
        rules_by_class = {}
        for rule in rules:
            for class_name in rule.classes:
                rules_by_class.setdefault(class_name, []).append(rule)
        if default_theme:
            default_theme = urlparse.urljoin(doc.base, default_theme)
        return cls(matchers, rules_by_class, default_theme=default_theme)

_meta_tag_re = re.compile(r'<meta\s+(.*?)>', re.I | re.S)
_http_equiv_re = re.compile(r'http-equiv=(?:"([^"]*)"|([^\s>]*))', re.I|re.S)
_content_re = re.compile(r'content=(?:"([^"]*)"|([^\s>]*))', re.I|re.S)
        
def parse_meta_headers(body):
    headers = []
    for match in _meta_tag_re.finditer(body):
        content = match.group(1)
        http_equiv_match = _http_equiv_re.search(content)
        content_match = _content_re.search(content)
        if not http_equiv_match or not content_match:
            ## FIXME: log partial matches?
            continue
        http_equiv = (http_equiv_match.group(1) or http_equiv_match.group(2) or '').strip()
        content = content_match.group(1) or content_match.group(2) or ''
        if not http_equiv or not content:
            ## FIXME: is empty content really meaningless?
            continue
        headers.append((http_equiv, content))
    return headers

standard_rule = Rule.parse_xml(XML('''\
<rule>
  <!-- FIXME: append-or-replace for title? -->
  <replace content="children:/html/head/title" theme="children:/html/head/title" nocontent="ignore" />
  <append content="elements:/html/head/link" theme="children:/html/head" nocontent="ignore" />
  <append content="elements:/html/head/script" theme="children:/html/head" nocontent="ignore" />
  <append content="elements:/html/head/style" theme="children:/html/head" nocontent="ignore" />
  <!-- FIXME: Any handling for overlapping/identical elements? -->
</rule>'''), 'deliverance.ruleset.standard_rule')

"""Implements the <ruleset> handler."""

import re
from lxml.html import tostring, document_fromstring
from lxml.etree import XML, Comment, parse
from webob.headerdict import HeaderDict
from deliverance.exceptions import AbortTheme, DeliveranceSyntaxError
from deliverance.pagematch import run_matches, Match, ClientsideMatch
from deliverance.rules import Rule, remove_content_attribs
from deliverance.util.filetourl import filename_to_url, url_to_filename
from deliverance.themeref import Theme
from urlparse import urljoin

class RuleSet(object):
    """
    Represents ``<ruleset>``, except for proxy/settings (which are
    handled elsewhere).

    This is a container for rules/actions.  It contains many
    ``<rule>`` objects.
    """

    def __init__(self, matchers, clientsides, rules_by_class, default_theme=None,
                 source_location=None):
        self.matchers = matchers
        self.clientsides = clientsides
        self.rules_by_class = rules_by_class
        self.default_theme = default_theme
        self.source_location = source_location

    def apply_rules(self, req, resp, resource_fetcher, log, default_theme=None):
        """
        Apply the whatever the appropriate rules are to the request/response.
        """
        extra_headers = parse_meta_headers(resp.body)
        if extra_headers:
            response_headers = HeaderDict(resp.headerlist + extra_headers)
        else:
            response_headers = resp.headers
        try:
            classes = run_matches(self.matchers, req, resp, response_headers, log)
        except AbortTheme:
            return resp
        if 'X-Deliverance-Page-Class' in response_headers:
            log.debug(self, "Found page class %s in headers", response_headers['X-Deliverance-Page-Class'].strip())
            classes.extend(response_headers['X-Deliverance-Page-Class'].strip().split())
        if 'deliverance.page_classes' in req.environ:
            log.debug(self, "Found page class in WSGI environ: %s", ' '.join(req.environ["deliverance.page_classes"]))
            classes.extend(req.environ['deliverance.page_classes'])
        if not classes:
            classes = ['default']
        rules = []
        theme = None
        for class_name in classes:
            ## FIXME: handle case of unknown classes
            ## Or do that during compilation?
            for rule in self.rules_by_class.get(class_name, []):
                if rule not in rules:
                    rules.append(rule)
                    if rule.theme:
                        theme = rule.theme
        if theme is None:
            theme = self.default_theme

        if theme is None and default_theme is not None:
            theme = Theme(href=default_theme, 
                          source_location=self.source_location)
            
        if theme is None:
            log.error(self, "No theme has been defined for the request")
            return resp

        try:
            theme_href = theme.resolve_href(req, resp, log)
            theme_doc = self.get_theme(theme_href, resource_fetcher, log)
            content_doc = self.parse_document(resp.body, req.url)

            run_standard = True
            for rule in rules:
                if rule.match is not None:
                    matches = rule.match(req, resp, response_headers, log)
                    if not matches:
                        log.debug(rule, "Skipping <rule>")
                        continue
                rule.apply(content_doc, theme_doc, resource_fetcher, log)
                if rule.suppress_standard:
                    run_standard = False
            if run_standard:
                ## FIXME: should it be possible to put the standard rule in the ruleset?
                standard_rule.apply(content_doc, theme_doc, resource_fetcher, log)
        except AbortTheme:
            return resp
        remove_content_attribs(theme_doc)
        ## FIXME: handle caching?

        content_tree = content_doc.getroottree()

        if "XHTML" in content_tree.docinfo.doctype:
            method = "xml"
        else:
            method = "html"

        ## FIXME: this seems like a terrible way to preserve the content's DOCTYPE
        if resp.body.strip().startswith("<!DOCTYPE"):
            theme_str = tostring(theme_doc)
            theme_str = content_tree.docinfo.doctype + theme_str
            theme_doc = document_fromstring(theme_str)
        tree = theme_doc.getroottree()

        resp.body = tostring(tree, method=method)
        return resp

    def check_clientside(self, req, log):
        for clientside in self.clientsides:
            if clientside(req, None, None, log):
                log.debug(clientside, '<clientside> matched request, using client-side theming')
                return True
        return False

    def get_theme(self, url, resource_fetcher, log):
        """
        Retrieves the theme at the given URL.  Also stores it in the
        log for later use by the log.
        """
        log.info(self, 'Fetching theme from %s' % url)
        log.theme_url = url
        ## FIXME: should do caching
        ## FIXME: check response status
        resp = resource_fetcher(url, retry_inner_if_not_200=True)
        if resp.status_int != 200:
            log.fatal(
                self, "The resource %s was not 200 OK: %s" % (url, resp.status))
            raise AbortTheme(
                "The resource %s returned an error: %s" % (url, resp.status))
        doc = self.parse_document(resp.body, url)
        self.make_links_absolute(doc)
        return doc

    def make_links_absolute(self, doc):
        base_url = doc.base_url
        def link_repl_preserve_internal(href):
            if href == '' or href[0] == '#':
                return href
            else:
                return urljoin(base_url, href)
        doc.rewrite_links(link_repl_preserve_internal)

    def parse_document(self, s, url):
        """
        Parses the given document as an HTML document.
        """
        return document_fromstring(s, base_url=url)

    def log_description(self, log=None):
        """Description for use in log messages"""
        if log is None:
            name = 'ruleset'
        else:
            name = '<a href="%s" target="_blank">ruleset</a>' % (
                log.link_to(self.source_location, source=True))
        desc = '&lt;%s&gt;' % name
        return desc

    @classmethod
    def parse_xml(cls, doc, source_location):
        """
        Parses the given XML/etree document into an instance of this
        class.
        """
        assert doc.tag == 'ruleset'
        matchers = []
        clientsides = []
        rules = []
        default_theme = None
        for el in doc.iterchildren():
            if el.tag == 'match':
                matcher = Match.parse_xml(el, source_location)
                matchers.append(matcher)
            elif el.tag == 'clientside':
                matcher = ClientsideMatch.parse_xml(el, source_location)
                clientsides.append(matcher)
            elif el.tag == 'rule':
                rule = Rule.parse_xml(el, source_location)
                rules.append(rule)
            elif el.tag == 'theme':
                ## FIXME: Add parse error
                default_theme = Theme.parse_xml(el, source_location)
            elif el.tag in ('proxy', 'server-settings', Comment):
                # Handled elsewhere, so we just ignore this element
                continue
            else:
                ## FIXME: source location?
                raise DeliveranceSyntaxError(
                    "Invalid tag %s (unknown tag name %r)" 
                    % (tostring(el).split('>', 1)[0]+'>', el.tag),
                    element=el)
        rules_by_class = {}
        for rule in rules:
            for class_name in rule.classes:
                rules_by_class.setdefault(class_name, []).append(rule)
        return cls(matchers, clientsides, rules_by_class, default_theme=default_theme,
                   source_location=source_location)

    @classmethod
    def parse_file(cls, filename):
        """Parse this from a filname"""
        file_url = filename_to_url(filename)
        tree = parse(filename, base_url=file_url)
        el = tree.getroot()
        tree.xinclude()
        return cls.parse_xml(el, file_url)

    def clientside_actions(self, req, resp, log):
        extra_headers = parse_meta_headers(resp.body)
        if extra_headers:
            response_headers = HeaderDict(resp.headerlist + extra_headers)
        else:
            response_headers = resp.headers
        try:
            classes = run_matches(self.matchers, req, resp, response_headers, log)
        except AbortTheme:
            assert 0, 'no abort should happen'
        if 'X-Deliverance-Page-Class' in response_headers:
            classes.extend(resp.headers['X-Deliverance-Page-Class'].strip().split())
        if 'deliverance.page_classes' in req.environ:
            classes.extend(req.environ['deliverance.page_classes'])
        if not classes:
            classes = ['default']
        rules = []
        for class_name in classes:
            ## FIXME: handle case of unknown classes
            ## Or do that during compilation?
            for rule in self.rules_by_class.get(class_name, []):
                if rule not in rules:
                    rules.append(rule)
                    if rule.theme:
                        assert 0, 'no rule themes should be present'
        content_doc = self.parse_document(resp.body, req.url)
        actions = []
        run_standard = True
        for rule in rules:
            if rule.match is not None:
                matches = rule.match(req, resp, response_headers, log)
                if not matches:
                    log.debug(rule, "Skipping <rule>")
                    continue
            actions.extend(rule.clientside_actions(content_doc, log))
            if rule.suppress_standard:
                run_standard = False
        if run_standard:
            ## FIXME: should it be possible to put the standard rule in the ruleset?
            actions.extend(standard_rule.clientside_actions(content_doc, log))
        return actions
        

_meta_tag_re = re.compile(r'<meta\s+(.*?)>', re.I | re.S)
_http_equiv_re = re.compile(r'http-equiv=(?:"([^"]*)"|([^\s>]*))', re.I|re.S)
_content_re = re.compile(r'content=(?:"([^"]*)"|([^\s>]*))', re.I|re.S)
        
def parse_meta_headers(body):
    """
    Returns a list of headers (in the form ``[(header_name,
    header_value)...]`` parsed from an HTML document, where the
    headers are in the format ``<meta http-equiv="header_name"
    content="header_value">``
    """
    headers = []
    for match in _meta_tag_re.finditer(body):
        content = match.group(1)
        http_equiv_match = _http_equiv_re.search(content)
        content_match = _content_re.search(content)
        if not http_equiv_match or not content_match:
            ## FIXME: log partial matches?
            continue
        http_equiv = (http_equiv_match.group(1) or http_equiv_match.group(2) or '')
        http_equiv = http_equiv.strip()
        content = content_match.group(1) or content_match.group(2) or ''
        if not http_equiv or not content:
            ## FIXME: is empty content really meaningless?
            continue
        headers.append((http_equiv, content))
    return headers

# Note: these are included in the documentation; any changes should be
# reflected there as well.
standard_rule = Rule.parse_xml(XML('''\
<rule>
  <!-- FIXME: append-or-replace for title? -->
  <!-- FIXME: maybe something like notheme="append:/html/head" -->
  <replace content="children:/html/head/title" 
           theme="children:/html/head/title" nocontent="ignore" />
  <prepend content="elements:/html/head/link" 
          theme="children:/html/head" nocontent="ignore" />
  <prepend content="elements:/html/head/script" 
          theme="children:/html/head" nocontent="ignore" />
  <prepend content="elements:/html/head/style" 
          theme="children:/html/head" nocontent="ignore" />
  <!-- FIXME: Any handling for overlapping/identical elements? -->
</rule>'''), 'deliverance.ruleset.standard_rule')

import unittest
import os
import sys
from lxml import etree
from formencode.doctest_xml_compare import xml_compare
from deliverance.interpreter import Renderer as PyRenderer
from deliverance.xslt import Renderer as XSLTRenderer
import copy 
import urllib

RENDERER_CLASSES = [ PyRenderer, XSLTRenderer ]

select_tests = []

class DeliveranceTestCase:

    def __init__(self, rules, rules_uri, theme, theme_uri, content, output, renderer_class):
        self.rules = rules
        self.rules_uri = rules_uri
        self.theme = theme
        self.theme_uri = theme_uri
        self.content = content
        self.output = output
        self.renderer_class = renderer_class

    def __call__(self, name):
        def reference_resolver(href, parse, encoding=None):
            f = urllib.urlopen(href)
            content = f.read()
            f.close()
            if parse == "xml":
                return etree.XML(content)
            elif encoding:
                return content.decode(encoding)

        renderer = self.renderer_class(
            theme=self.theme,
            theme_uri=self.theme_uri,
            rule=self.rules, rule_uri=self.rules_uri,
            reference_resolver=reference_resolver)
        actual = renderer.render(self.content)
        reporter = []
        result = xml_compare(actual, self.output, reporter.append)
        if not result:
            raise ValueError(
                "Comparison failed between actual:\n==================\n%s\n\nexpected:\n==================\n%s\n\nReport:\n%s"
                % (strify(actual), strify(self.output), '\n'.join(reporter)))

def strify(el):
    return etree.tostring(el, xml_declaration=False, pretty_print=True)

##################################################
## Test Suite construction
##################################################

test_dir = os.path.join(os.path.dirname(__file__), 'test-data')

def test_examples():
    for renderer_class in RENDERER_CLASSES:
        for fn in os.listdir(test_dir):
            fn = os.path.join(test_dir, fn)
            for case in cases(fn,renderer_class):
                yield case

def cases(fn, renderer_class):
    basename = os.path.basename(fn)
    if not basename.startswith('test_'):
        return
    if fn.endswith('~'):
        return
    if select_tests and basename not in select_tests:
        return
    try:
        doc = etree.parse(fn)
    except etree.XMLSyntaxError, e:
        e.args += (('in file %s' % fn), )
        raise
    for index, el in enumerate(doc.findall('deliverance-test')):
        index += 1
        rules = el.find('{http://www.plone.org/deliverance}rules')
        assert rules is not None, (
            "No rules found in %s:%s" % (fn, index))


        theme = el.find('theme')
        themebody = None
        if (len(theme)):
            themebody = copy.deepcopy(theme[0])
        theme[:] = []

        content = el.find('content')
        contentbody = None
        if (len(content)):
            contentbody = copy.deepcopy(content[0])
        content[:] = []


        output = el.find('output')
        outputbody = None
        if (len(output)):
            outputbody = copy.deepcopy(output[0])
        output[:] = []

        case = DeliveranceTestCase(
            rules=rules,
            rules_uri = fn,
            theme=themebody,
            theme_uri=el.find('theme').attrib['base'],
            content=contentbody,
            output=outputbody, 
            renderer_class=renderer_class)
        yield case, ('[%s] %s:%s' % (renderer_class, fn, index))




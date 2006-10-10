import sys 
from lxml import etree
from htmlserialize import tostring
import urllib
from interpreter import Renderer as PythonRenderer
from xslt import Renderer as XSLTRenderer
from optparse import OptionParser
import re
import os
from time import time

"""
Tests the relative speed of the Python and XSLT renderers

"""


DEFAULT_BASE_URL = "http://www.example.com"


def grab_url(url):
    f = open(url)
    data = f.read()
    f.close()
    return data

def do_transform(renderer_type, theme_url, base_url, rules_url, content_url):
    rules = etree.XML(grab_url(rules_url))
    theme = etree.HTML(grab_url(theme_url))
    content = etree.HTML(grab_url(content_url))
    
    def reference_resolver(href, parse, encoding=None):
        if not href.startswith('/'):
            href = os.path.join(os.path.dirname(rules_url),href)
        text = grab_url(href)
        if parse == "xml":
            return etree.XML(text)
        elif encoding:
            return text.decode(encoding)

    start = time()
    iters = 1000
    for i in range(iters):
        renderer = None
        if renderer_type == 'xslt':
            renderer = XSLTRenderer(theme,base_url,rules,reference_resolver)
        elif renderer_type == 'py':
            renderer = PythonRenderer(theme,base_url,rules,reference_resolver)
        else:
            print "Unknown renderer type '" + renderer_type + "'"
            return etree.Element("error")
        renderer.render(content)

    print "Renderer: " + renderer_type
    print "*** time:", time() - start , " for " , iters, " iterations ***\n"

    return
        

def parse_blend_file(filename):
    b = etree.XML(open(filename).read())
    return b.get('theme'),b.get('baseurl'),b.get('rules')


def die(message,parser):
    print message
    parser.print_usage()
    sys.exit(0)    
    
if __name__ == '__main__':
    do_transform('xslt','test-data/nycsr/nycsr_speed.html','http://www.nycsr.org','test-data/nycsr/nycsr.xml','test-data/nycsr/openplans.html')
    do_transform('py','test-data/nycsr/nycsr_speed.html','http://www.nycsr.org','test-data/nycsr/nycsr.xml','test-data/nycsr/openplans.html')
    

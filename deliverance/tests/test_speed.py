import sys 
from lxml import etree
from deliverance.htmlserialize import tostring
import urllib
from deliverance.interpreter import Renderer as PythonRenderer
from deliverance.xslt import Renderer as XSLTRenderer
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

    if renderer_type == 'xslt':
        renderer_class = XSLTRenderer
    elif renderer_type == 'py':
        renderer_class = PythonRenderer
    else:
        print "Unknown renderer type '" + renderer_type + "'"
        return etree.Element("error")

    renderer = renderer_class(theme,base_url,rules,'.',reference_resolver)

    start = time()
    iters = 3000
    for i in range(iters):
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
    
def main(args=None):
    do_transform('xslt','deliverance/test-data/nycsr/nycsr_speed.html','http://www.nycsr.org','deliverance/test-data/nycsr/nycsr.xml','deliverance/test-data/nycsr/openplans.html')
    do_transform('py','deliverance/test-data/nycsr/nycsr_speed.html','http://www.nycsr.org','deliverance/test-data/nycsr/nycsr.xml','deliverance/test-data/nycsr/openplans.html')
    
if __name__ == '__main__':
    main()

import sys 
from lxml import etree
from htmlserialize import tostring
import urllib
from interpreter import Renderer as PythonRenderer
from xslt import Renderer as XSLTRenderer
from optparse import OptionParser
import re
import os 

"""
Command line utility to run a deliverance transform 
given the urls of the rules, theme and content. 


themeurl, rulesfile and baseurl can be rolled into a file specified with -f 
it should contain an element like 
<blend theme="themeurl" baseurl="baseurl" rules="rulesfile" />
"""


DEFAULT_BASE_URL = "http://www.example.com"

usage = "usage: %prog [options] <content_url>"
parser = OptionParser(usage=usage)
parser.add_option("-t", "--theme", dest="theme_url", help="url of theme html")
parser.add_option("-b", "--baseurl", dest="base_url",
                  help="relative urls in the theme will be made absolute relative to this url [default %default]", 
                  default=DEFAULT_BASE_URL)
parser.add_option("-r", "--rules", dest="rules_file",
                  help="path to file containing the deliverance rules to apply")
parser.add_option("-f", "--from-file", dest="blend_file",
                  help="take theme, baseurl and rules parameters from the referenced file")
parser.add_option("-R", "--renderer", dest="renderer_type",
                  help="(xslt|py) [default %default]", default="xslt", choices=['xslt','py'])



def grab_url(url):
    """
    returns the data referenced by the url provided. 
    """
    f = urllib.urlopen(url)
    data = f.read()
    f.close()
    return data

def do_transform(renderer_type, theme_url, base_url, rules_url, content_url):
    """
    Perform the deliverance transform using the rules referenced by rules_url
    on the pages referenced by theme_url and content_url. Renderer type determines
    which deliverance renderer class is used to perform the transform, which may be 
    either 'xslt' or 'py'. Relative urls in the theme page will rewritten as 
    absolute urls relative to the base_url given. returns the result of the 
    transformation 
    """
    rules = etree.XML(grab_url(rules_url))
    theme = etree.HTML(grab_url(theme_url))
    content = etree.HTML(grab_url(content_url))
    
    def reference_resolver(href, parse, encoding=None):
        text = grab_url(href)
        if parse == "xml":
            return etree.XML(text)
        elif encoding:
            return text.decode(encoding)

    renderer = None
    if renderer_type == 'xslt':
        renderer = XSLTRenderer(theme,base_url,rules,rules_url,reference_resolver)
    elif renderer_type == 'py':
        renderer = PythonRenderer(theme,base_url,rules,rules_url,reference_resolver)
    else:
        print "Unknown renderer type '" + renderer_type + "'"
        return etree.Element("error")

    return renderer.render(content)
        

def parse_blend_file(filename):
    """
    returns the theme url, base url and rules url 
    specified in the file given. filename is 
    expected to contain an xml document containing a 
    toplevel element with attributes 'theme', 
    'baseurl' and 'rules'
    """
    b = etree.XML(open(filename).read())
    return b.get('theme'),b.get('baseurl'),b.get('rules')


def die(message,parser):
    """
    prints an error message, the usage of the program, 
    then quits. 
    """
    print message
    parser.print_usage()
    sys.exit(0)    
    
def main(args=None):
    """
    main function, see usage information 
    """
    if args is None:
        args = sys.argv[1:]

    options, args = parser.parse_args(args)
    
    if len(args) == 0:
        die("no content url specified.", parser)

    content_url = args[0]
    theme_url = None
    base_url = None
    rules_file = None
        

    if options.blend_file:
        if (options.rules_file or options.theme_url or options.base_url != DEFAULT_BASE_URL):
            die("cannot specify base url, rules file or theme url when taking parameters from file.",parser)

        try:
            theme_url, base_url, rules_file = parse_blend_file(options.blend_file)            

        except Exception, message:
            die(message, parser)

    else:
        theme_url = options.theme_url
        rules_file = options.rules_file
        base_url = options.base_url


    if theme_url is None:
        die("no theme url specified.",parser)

    if rules_file is None:
        die("no rules file specified.",parser)

    if base_url is None:
        die("no base url specified",parser)
        

    print tostring(do_transform(options.renderer_type,
                                theme_url,
                                base_url,
                                rules_file,
                                content_url))
    

if __name__ == '__main__':
    main()

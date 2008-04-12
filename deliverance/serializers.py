from lxml import etree
from htmlserialize import tostring

def HTML4(environ, content):
    return tostring(content,
                    doctype_pair=("-//W3C//DTD HTML 4.01 Transitional//EN",
                                  "http://www.w3.org/TR/html4/loose.dtd"))

def XHTML(environ, content):
    return '<?xml version="1.0"?>' + \
            '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">'+ \
            etree.tostring(content)

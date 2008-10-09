from paste.script.templates import Template, var
from tempita import paste_script_template_renderer
import os
import posixpath
import urllib2
from lxml.html import parse, tostring
import mimetypes

class DeliveranceTemplate(Template):
    _template_dir = 'paster-templates/deliverance'
    template_renderer = staticmethod(paste_script_template_renderer)
    summary = "Basic template for a deliverance-proxy setup"
    vars = [
        var('host', 'The host/port to serve on',
            'localhost:8000'),
        var('proxy_url', 'The main site to connect/proxy to', 
            default='http://localhost:8080'),
        var('proxy_rewrite_links', 'Rewrite links from sub_host?',
            default='n'),
        var('password', 'The password for the deliverance admin console'),
        var('theme_url', 'A URL to pull the initial theme from (optional)'),
        ]

    def post(self, command, output_dir, vars):
        theme_url = vars['theme_url']
        if not theme_url:
            content = DEFAULT_THEME_CONTENT
            files = DEFAULT_FILES
        else:
            content, files = self.get_content(theme_url)
        command.ensure_file(os.path.join(output_dir, 'theme/theme.html'), content)
        for filename, content in files:
            command.ensure_file(os.path.join(output_dir, 'theme', filename), content)

    def get_content(self, url):
        """Gets the content and all embedded content (images, CSS, etc)"""
        print 'Fetching theme at %s' % url
        page = parse(urllib2.urlopen(url)).getroot()
        page.make_links_absolute()
        files = []
        for element, attr, link, pos in page.iterlinks():
            if not self._embedded_link(element):
                continue
            filename, content = self.get_embedded(link)
            if not filename:
                continue
            files.append((filename, content))
            if attr is None:
                old_value = element.text
            else:
                old_value = unicode(element.attrib[attr])
            new_value = old_value[:pos] + filename + old_value[pos+len(link):]
            if attr is None:
                element.text = new_value
            else:
                element.attrib[attr] = new_value
        return tostring(page), files

    def _embedded_link(self, element):
        """True if the element links to something embedded"""
        if element.tag in ('script', 'img', 'style'):
            return True
        if element.tag == 'link' and element.attrib.get('rel', '').lower() == 'stylesheet':
            return True
        return False

    def get_embedded(self, url):
        print '  fetching %s' % url
        try:
            resp = urllib2.urlopen(url)
        except urllib2.HTTPError, e:
            print 'Could not fetch %s: %s' % (url, e)
            return None, None
        url = resp.geturl()
        content = resp.read()
        content_type = resp.info()['content-type']
        filename = posixpath.basename(url).split('?')[0]
        filename, orig_ext = posixpath.splitext(filename)
        if not filename:
            filename = 'embedded'
        ext = mimetypes.guess_extension(content_type)
        if ext == '.jpeg' or ext == 'jpe':
            ext = '.jpg'
        ext = ext or orig_ext
        return filename + ext, content

DEFAULT_THEME_CONTENT = '''\
<html>
 <head>
  <title></title>
  <link rel="stylesheet" type="text/css" href="style.css">
 </head>
 <body>
  <div id="content">
    content that will be replaced.
  </div>
 </body>
</html>
'''

DEFAULT_FILES = [
    ('style.css', '/* put your styles here */'),
    ]

class PloneTemplate(Template):
    _template_dir = 'paster-templates/plone'
    required_templates = ['deliverance']
    template_renderer = staticmethod(paste_script_template_renderer)
    summary = 'Plone-specific template for deliverance-proxy'
    vars = [
        var('site_name', "The name of your Plone site (no /'s)"),
        ]

"""Application that allows you to edit files."""
from webob import Request, Response, exc
from tempita import HTMLTemplate
import os
import urllib
from paste.urlparser import StaticURLParser

class Editor(object):

    def __init__(self, base_dir=None, filename=None,
                 title=None, force_syntax=None):
        assert base_dir or filename
        assert not base_dir or not filename
        if base_dir:
            self.base_dir = os.path.normcase(os.path.abspath(base_dir))
        else:
            self.base_dir = None
        self.filename = filename
        self.title = title
        self.force_syntax = force_syntax

    def __call__(self, environ, start_response):
        req = Request(environ)
        if req.path_info_peek() == '.media':
            req.path_info_pop()
            app = StaticURLParser(os.path.join(os.path.dirname(__file__), 'media'))
            return app(environ, start_response)
        if self.base_dir:
            filename = os.path.join(self.base_dir, req.path_info.lstrip('/'))
            assert filename.startswith(self.base_dir)
        else:
            filename = self.filename
        if req.method == 'POST':
            resp = self.save_file(req, filename)
        elif req.method == 'GET':
            resp = self.edit_file(req, filename)
        else:
            assert 0, 'bad method: %r' % req.method
        return resp(environ, start_response)

    def edit_url(self, req, filename):
        if self.filename:
            assert self.filename == filename
            return req.application_url
        else:
            assert filename.startswith(self.base_dir)
            filename = filename[len(self.base_dir):].lstrip('/').lstrip('\\')
            return req.application_url + '/' + filename

    def save_file(self, req, filename):
        content = req.POST['content']
        f = open(filename, 'wb')
        f.write(content)
        f.close()
        return exc.HTTPFound(
            location=self.edit_url(req, filename))

    syntax_map = {
        '.c': 'c',
        '.cf': 'coldfusion',
        '.cpp': 'cpp',
        '.c++': 'cpp',
        '.css': 'css',
        '.html': 'html',
        '.htm': 'html',
        '.xhtml': 'html',
        '.js': 'js',
        '.pas': 'pas',
        '.pl': 'perl',
        '.php': 'php',
        '.py': 'python',
        'robots.txt': 'robotstxt',
        '.rb': 'ruby',
        '.sql': 'sql',
        '.tsql': 'tsql',
        '.vb': 'vb',
        '.xml': 'xml',
        }

    def edit_file(self, req, filename):
        f = open(filename, 'rb')
        content = f.read()
        f.close()
        title = self.title or filename
        syntax = None
        if self.force_syntax:
            syntax = self.force_syntax
        else:
            basename = os.path.basename(filename)
            if basename in self.syntax_map:
                syntax = self.syntax_map[basename]
            else:
                ext = os.path.splitext(filename)[1].lower()
                if ext in self.syntax_map:
                    syntax = self.syntax_map[ext]
        body = self.edit_template.substitute(
            content=content, filename=filename, title=title, 
            req=req, edit_url=self.edit_url(req, filename),
            syntax=syntax)
        resp = Response(body=body)
        resp.cache_expires()
        return resp

    edit_template = HTMLTemplate.from_filename(
        os.path.join(os.path.dirname(__file__), 'editor_template.html'))

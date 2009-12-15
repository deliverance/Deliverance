"""Application that allows you to edit files."""
from webob import Request, Response, exc
from tempita import HTMLTemplate
import os
from paste.urlparser import StaticURLParser
import mimetypes

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
        if req.method not in ('GET', 'POST'):
            resp = exc.HTTPMethodNotAllowed('Bad method: %s' % req.method,
                                            allow='GET,POST')
        elif os.path.isdir(filename):
            if req.method == 'POST':
                resp = self.save_create(req, filename)
            else:
                if not req.path.endswith('/'):
                    resp = exc.HTTPMovedPermanently(add_slash=True)
                else:
                    resp = self.view_dir(req, filename)
        else:
            if req.method == 'POST':
                resp = self.save_file(req, filename)
            elif req.method == 'GET':
                resp = self.edit_file(req, filename)
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

    def syntax_for_filename(self, filename):
        if self.force_syntax:
            return self.force_syntax
        basename = os.path.basename(filename)
        if basename in self.syntax_map:
            return self.syntax_map[basename]
        else:
            ext = os.path.splitext(filename)[1].lower()
            if ext in self.syntax_map:
                return self.syntax_map[ext]
        mimetype, enc = mimetypes.guess_type(os.path.splitext(filename)[1])
        if mimetype.startswith('application/') and mimetype.endswith('+xml'):
            return 'xml'
        return None

    def edit_file(self, req, filename):
        f = open(filename, 'rb')
        content = f.read()
        f.close()
        title = self.title or filename
        syntax = self.syntax_for_filename(filename)
        body = self.edit_template.substitute(
            content=content, filename=filename, title=title, 
            req=req, edit_url=self.edit_url(req, filename),
            syntax=syntax)
        resp = Response(body=body)
        resp.cache_expires()
        return resp

    edit_template = HTMLTemplate.from_filename(
        os.path.join(os.path.dirname(__file__), 'editor_template.html'))

    def save_create(self, req, dir):
        file = req.POST.get('file')
        if file is None or file == '':
            content = req.POST['content']
            filename = req.POST['filename']
        else:
            content = file.value
            filename = req.POST.get('filename') or file.filename
        filename = filename.replace('\\', '/')
        filename = os.path.basename(os.path.normpath(filename))
        filename = os.path.join(dir, filename)
        if os.path.exists(filename):
            return exc.HTTPForbidden(
                "The file %s already exists, you cannot upload over it" % filename)
        f = open(filename, 'wb')
        f.write(content)
        f.close()
        return exc.HTTPFound(
            location=self.edit_url(req, filename))

    skip_files = ['.svn', 'CVS', '.hg']

    def view_dir(self, req, dir):
        dir = os.path.normpath(dir)
        show_parent = dir != self.base_dir
        children = [os.path.join(dir, name) for name in os.listdir(dir)
                    if name not in self.skip_files]
        def edit_url(filename):
            return self.edit_url(req, filename)
        title = self.title or dir
        body = self.view_dir_template.substitute(
            req=req,
            dir=dir,
            show_parent=show_parent,
            title=title,
            basename=os.path.basename,
            dirname=os.path.dirname,
            isdir=os.path.isdir,
            children=children,
            edit_url=edit_url,
            )
        resp = Response(body=body)
        resp.cache_expires()
        return resp

    view_dir_template = HTMLTemplate.from_filename(
        os.path.join(os.path.dirname(__file__), 'view_dir_template.html'))

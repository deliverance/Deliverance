"""Simple HTTP Server.

This module builds on BaseHTTPServer by implementing the standard GET
and HEAD requests in a fairly straightforward manner.

"""


__version__ = "0.6"

__all__ = ["ThemedHTTPRequestHandler"]

import os
import mimetypes
import BaseHTTPServer
import SimpleHTTPServer
from StringIO import StringIO

from deliverance import AppMap
appmap = AppMap()


class ThemedHTTPRequestHandler(SimpleHTTPServer.SimpleHTTPRequestHandler):

    def send_head(self):
        """Common code for GET and HEAD commands.

        This sends the response code and MIME headers.

        Return value is either a file object (which has to be copied
        to the outputfile by the caller unless the command was HEAD,
        and must be closed by the caller under all circumstances), or
        None, in which case the caller has nothing further to do.

        """
        path = self.translate_path(self.path)
        f = None
        if os.path.isdir(path):
            for index in "index.html", "index.htm":
                index = os.path.join(path, index)
                if os.path.exists(index):
                    path = index
                    break
            else:
                return self.list_directory(path)
        ctype = self.guess_type(path)
        try:
            # Always read in binary mode. Opening files in text mode may cause
            # newline translations, making the actual size of the content
            # transmitted *less* than the content-length!
            
            # This is where we apply theming
            
            # First check to see if there is a query string.  If so, presume that 
            # to mean they want the source version.
            qs = len(self.path.split("?"))
            if ctype == "text/html" and qs == 1:
                print "Applying theme to", path
                xmlstring = open(path, "r").read()
                response = appmap.publish(xmlstring)
                f = StringIO(response)
                responsesize = str(len(xmlstring))
            else:
                f = open(path, 'rb')
                responsesize = str(os.fstat(f.fileno())[6])
        except IOError:
            self.send_error(404, "File not found")
            return None
        self.send_response(200)
        self.send_header("Content-type", ctype)
        self.send_header("Content-Length", responsesize)
        self.end_headers()
        return f

    extensions_map = mimetypes.types_map.copy()
    extensions_map.update({
        '': 'application/octet-stream', # Default
        '.py': 'text/plain',
        '.c': 'text/plain',
        '.h': 'text/plain',
        '.ico': 'image/x-icon',
        })

    

def test(HandlerClass = ThemedHTTPRequestHandler,
         ServerClass = BaseHTTPServer.HTTPServer):
    BaseHTTPServer.test(HandlerClass, ServerClass)


if __name__ == '__main__':
    test()

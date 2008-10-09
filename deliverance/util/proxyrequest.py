import webob
import chardet

class Response(webob.Response):
    default_charset = None
    unicode_errors = 'replace'

    def _unicode_body__get(self):
        """
        Get/set the unicode value of the body (using the charset of the Content-Type)
        """
        if not self.charset:
            guess = chardet.detect(self.body)
            self.charset = guess['encoding']
        body = self.body
        return body.decode(self.charset, self.unicode_errors)

    def _unicode_body__set(self, value):
        if not self.charset:
            raise AttributeError(
                "You cannot access Response.unicode_body unless charset is set")
        if not isinstance(value, unicode):
            raise TypeError(
                "You can only set Response.unicode_body to a unicode string (not %s)" % type(value))
        self.body = value.encode(self.charset)

    def _unicode_body__del(self):
        del self.body

    unicode_body = property(_unicode_body__get, _unicode_body__set, _unicode_body__del, doc=_unicode_body__get.__doc__)

class Request(webob.Request):
    ResponseClass = Response

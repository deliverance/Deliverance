"""
Represents <theme> elements
"""
from deliverance.exceptions import DeliveranceSyntaxError, AbortTheme
from deliverance.pyref import PyReference, PyArgs
import urlparse

class Theme(object):
    """
    Represents the <theme> element
    """

    def __init__(self, href=None, pyref=None, pyargs=None, source_location=None):
        self.href = href
        self.pyref = pyref
        self.pyargs = pyargs
        self.source_location = source_location

    @classmethod
    def parse_xml(cls, el, source_location):
        assert el.tag == 'theme'
        href = el.get('href')
        pyref = el.get('pyref')
        pyargs = PyArgs.from_attrib(el.attrib)
        if not pyref and pyargs:
            raise DeliveranceSyntaxError(
                'You cannot provide arguments (like %s) unless you provide a pyref attribute'
                % pyargs,
                element=el)
        if pyref:
            pyref = PythonReference.parse(pyref, source_location, 
                                          default_function='get_theme',
                                          default_objs=dict(AbortTheme=AbortTheme))
        if not pyref and not href:
            ## FIXME: also warn when pyref and href?
            raise DeliveranceSyntaxError(
                'You must provide at least one of href, pymodule, or the pyfile attribute',
                element=el)
        return cls(href=href, pyref=pyref,
                   pyargs=pyargs, source_location=source_location)

    def resolve_href(self, req, resp, log):
        if self.pyref:
            href = self.pyref(req, resp, log, **self.pyargs.dict)
        else:
            href = self.href
        ## FIXME: is this join a good idea?
        if href:
            href = urlparse.urljoin(req.url, href)
        return href

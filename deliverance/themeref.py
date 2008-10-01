"""
Represents <theme> elements
"""

import posixpath
import urlparse
from deliverance.exceptions import DeliveranceSyntaxError, AbortTheme
from deliverance.pyref import PyReference
from deliverance.security import execute_pyref
from deliverance.util.uritemplate import uri_template_substitute
from deliverance.util.nesteddict import NestedDict

class Theme(object):
    """
    Represents the <theme> element
    """

    def __init__(self, href=None, pyref=None, source_location=None):
        self.href = href
        self.pyref = pyref
        self.source_location = source_location

    @classmethod
    def parse_xml(cls, el, source_location):
        """Parse an instance from an etree XML element"""
        assert el.tag == 'theme'
        href = el.get('href')
        pyref = PyReference.parse_xml(el, source_location, default_function='get_theme',
                                      default_objs=dict(AbortTheme=AbortTheme))
        if not pyref and not href:
            ## FIXME: also warn when pyref and href?
            raise DeliveranceSyntaxError(
                'You must provide at least one of href, pymodule, or the '
                'pyfile attribute', element=el)
        return cls(href=href, pyref=pyref,
                   source_location=source_location)

    def resolve_href(self, req, resp, log):
        """Figure out the theme URL given a request and response.

        This calls the pyref, or does URI template substitution on an
        href attribute"""
        substitute = True
        if self.pyref:
            if not execute_pyref(req):
                log.error(
                    self, "Security disallows executing pyref %s" % self.pyref)
                ## FIXME: this isn't very good; fatal exception?:
                href = self.href
            else:
                href = self.pyref(req, resp, log)
                substitute = False
        else:
            href = self.href
        if substitute:
            vars = NestedDict(req.environ, req.headers, 
                              dict(here=posixpath.dirname(self.source_location)))
            new_href = uri_template_substitute(href, vars)
            if new_href != href:
                log.debug(
                    self, 'Rewrote theme href="%s" to "%s"' % (href, new_href))
                href = new_href
        ## FIXME: is this join a good idea?
        if href:
            href = urlparse.urljoin(req.url, href)
        return href

"""
Deliverance theming for mod_python filters

Deliverance applies a theme to content.  This mod_python module acts as an 
Apache "filter", transforming content as it passes through Apache.

This module gets imported by mod_python during its startup.  Thus, the 
thememap instance becomes a global, computed only once.  If you need to 
recompute the theme, for example, restart the Apache.
"""
from cStringIO import StringIO

from mod_python import apache
from thememap import ThemeMap
thememap = ThemeMap() # Themes are generated once at module import time


def outputfilter(filter):
    
    if (filter.req.main or
        not filter.req.content_type == "text/html"):
        
        # Presence of filter.req.main tells us that
        # we are in a subrequest. We don't want to theme
        # the data more than once, so we pass_on() in
        # subrequests. We also pass_on() if the the content-type
        # isn't text/html.

        filter.pass_on()

    # Theme switching
    # Look in the request arguments for a named theme
    if not hasattr(filter.req, 'theme'):
        # Check for a flag to not apply theme
        args = filter.req.args
        if args and args.find("theme") > -1:
            # XXX need a better arg parser here
            filter.req.theme = args.split("=")[1]
        else:
            filter.req.theme = "default"
            
    # If notheme, stop processing
    if filter.req.theme == "notheme":
        filter.pass_on()

    # Create stream buffer
    # Since the filter might be called multiple times, create 
    # a place to hold content as it gets accumulated from chunks.
    try:
        streambuffer = filter.req.streambuffer
    except AttributeError:
        filter.req.streambuffer = StringIO()
        streambuffer = filter.req.streambuffer

    # Read in the content available in the filter and add 
    # it to that read earlier
    buff = filter.read()
    while buff:
        streambuffer.write(buff)
        buff = filter.read()

    if buff is None:
        # Looks like the request is finished and this is the 
        # last call by Apache into this filter.
        themeid = filter.req.theme
        xmlstring = streambuffer.getvalue()
        output = thememap.applyTheme(xmlstring, themeid)
        filter.write(output)
        filter.close()

"""
Deliverance theming for mod_python filters

Deliverance applies a theme to content.  This mod_python module acts as an 
Apache "filter", transforming content as it passes through Apache.

This module gets imported by mod_python during its startup.  Thus, the 
appmap instance becomes a global, computed only once.  If you need to 
recompute the theme, for example, restart the Apache.
"""
from cStringIO import StringIO

from mod_python import apache
from deliverance import AppMap
appmap = AppMap() # Theme is generated once at module import time

def outputfilter(filter):

    if not hasattr(filter.req, 'notheme'):
        # Check for a flag to not apply theme
        args = filter.req.args
        if args and args.find("notheme") > -1:
            filter.req.notheme = True
        else:
            filter.req.notheme = False

    try:
        streambuffer = filter.req.streambuffer
    except AttributeError:
        filter.req.streambuffer = StringIO()
        streambuffer = filter.req.streambuffer

    streamlet = filter.readline()
    while streamlet:
        streambuffer.write(streamlet)
        streamlet = filter.readline()

    if streamlet is None:
        try:
            del filter.req.headers_out["Content-Length"]
        except KeyError:
            pass            
        if filter.req.notheme:
            filter.write(streambuffer.getvalue())
        else:
            filter.write(appmap.publish(streambuffer.getvalue()))
        filter.close()


def handler(req):
    """Basic filter applying to all mime types it is registered for"""

    # Get the path, strip off leading slash, and convert to a 
    # dotted notation for xml:id compatibility
    path_info = req.path_info[1:]
    dotted_path = path_info.replace("/", ".")

    response = appmap.publish(dotted_path)
    req.content_type = "text/html"
    req.write(response)

    return apache.OK

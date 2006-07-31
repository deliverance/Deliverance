"""
mphandler - mod_python content handler for Deliverance

This module bridges an Apache content handler, implemented in 
mod_python, to a Deliverance 'content map'.  The content map is 
an in-memory tree of resources, as XML, that can be rendered 
into XHTML.

In most cases, the output of this handler is then the input to 
a Deliverance theme.
"""

from mod_python import apache
from contentmap import ContentMap
contentmap = ContentMap() # Called once at module import time

def handler(req):
    """Basic filter applying to all mime types it is registered for"""

    # Get the path, strip off leading slash, and convert to a 
    # dotted notation for xml:id compatibility
    path_info = req.path_info[1:]
    dotted_path = path_info.replace("/", ".")

    response = contentmap.publish(dotted_path)
    req.content_type = "text/html"
    req.write(response)

    return apache.OK

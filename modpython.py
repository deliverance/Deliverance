"""
Deliverance publisher for mod_python

This module gets imported by mod_python during its startup.  Thus, the 
appmap instance becomes a global, computed only once.  If you need to 
recompute the theme, for example, restart the Apache.
"""

from mod_python import apache
from deliverance import AppMap
appmap = AppMap()

def handler(req):
    """Basic handler applying to all mime types it is registered for"""

    # Get the path, strip off leading slash, and convert to a 
    # dotted notation for xml:id compatibility
    path_info = req.path_info[1:]
    dotted_path = path_info.replace("/", ".")
    
    response = appmap.publish(dotted_path)
    req.content_type = "text/html"
    req.write(response)

    return apache.OK

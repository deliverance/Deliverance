"""
This sets up an example site
"""

import os
import sys
from paste.urlparser import StaticURLParser
from paste.httpserver import serve
from weberror.evalexception import EvalException
from deliverance.middleware import DeliveranceMiddleware, FileRuleGetter
from deliverance.security import SecurityContext

base_path = os.path.join(os.path.dirname(__file__), 'example-files')
app = StaticURLParser(base_path)
rules_file = os.path.join(base_path, 'rules.xml')
deliv_app = DeliveranceMiddleware(app, FileRuleGetter(rules_file))
full_app = SecurityContext.middleware(deliv_app, execute_pyref=True, display_logging=True, display_local_files=True,
                                      force_dev_auth=True)

if __name__ == '__main__':
    try:
        port = sys.argv[1]
    except IndexError:
        port = '8080'
    host = '127.0.0.1'
    if ':' in port:
        host, port = port.split(':')
    print 'See http://%s:%s/?deliv_log for the page with log messages' % (host, port)
    serve(EvalException(full_app), port=port, host=host)

"""
This sets up an example site
"""

import os
from paste.urlparser import StaticURLParser
from paste.httpserver import serve
from weberror.evalexception import EvalException
from deliverance.middleware import DeliveranceMiddleware, RulesetGetter
from deliverance.security import SecurityContext

base_path = os.path.join(os.path.dirname(__file__), 'example-files')
app = StaticURLParser(base_path)
deliv_app = DeliveranceMiddleware(app, RulesetGetter('/rules.xml'))
full_app = SecurityContext.middleware(deliv_app, execute_pyref=True, display_logging=True, display_local_files=True,
                                      force_dev_auth=True)

if __name__ == '__main__':
    print 'See http://127.0.0.1:8080/?deliv_log for the page with log messages'
    serve(EvalException(full_app))

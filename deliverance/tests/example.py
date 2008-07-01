"""
This sets up an example site
"""

import os
from paste.urlparser import StaticURLParser
from paste.httpserver import serve
from weberror.evalexception import EvalException
from deliverance.middleware import DeliveranceMiddleware, SubrequestRuleGetter

base_path = os.path.join(os.path.dirname(__file__), 'example-files')
app = StaticURLParser(base_path)
deliv_app = DeliveranceMiddleware(app, SubrequestRuleGetter('/rules.xml'))

if __name__ == '__main__':
    serve(EvalException(deliv_app))

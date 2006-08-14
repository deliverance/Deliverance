import os
from deliverance.main import AppMap
from deliverance.wsgifilter import DeliveranceMiddleware
from paste.urlparser import StaticURLParser
from paste.fixture import TestApp

here = os.path.dirname(__file__)
test_data = os.path.join(here, 'test-data')

static_app = StaticURLParser(test_data)

wrapped_app = DeliveranceMiddleware(
    static_app, AppMap(os.path.join(test_data, 'etc')))

app = TestApp(wrapped_app)

def test_filter():
    root = app.get('/')
    print root
    assert 0
    

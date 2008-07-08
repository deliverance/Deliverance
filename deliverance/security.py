class SecurityContext(object):
    """
    This represents the security context of the Deliverance request.
    This is stored in ``environ['deliverance.security_context']`` and
    is local to the request.

    The three primary security-related restrictions are:
    
    1. Can Python be executed using pyref attributes?
    2. Can logging messages be displayed?
    3. Can local files be displayed?

    Each of these is a method that takes the request.

    When instantiating, the default value of None means that the value
    should be guessed from the environment.

    This uses the `developer auth spec
    <http://wsgi.org/wsgi/Specifications/developer_auth>`_ for
    guessing when a value is None.
    """

    def __init__(self, execute_pyref=False, display_logging=None,
                 display_local_files=None):
        self._execute_pyref = execute_pyref
        self._display_logging = display_logging
        self._display_local_files = display_local_files
    
    @classmethod
    def install(cls, environ, **kw):
        """
        Instantiate the context and put it into the environment
        """
        inst = cls(**kw)
        environ['deliverance.security_context'] = cls(**kw)
        return inst
    
    def display_logging(self, environ):
        if self._display_logging is not None:
            return self._display_logging
        return self.is_developer_user(environ)

    def display_local_files(self, environ):
        if self._display_logging is not None:
            return self._display_logging
        return self.is_developer_user(environ)

    def execute_pyref(self, environ):
        return self._execute_pyref

    def is_developer_user(self, environ):
        if hasattr(environ, 'environ'):
            # Actually a request
            environ = environ.environ
        return bool(environ.get('x-wsgiorg.developer_user'))

    @classmethod
    def middleware(cls, app, **settings):
        """
        Wrap the application with middleware that installs settings
        with the given configuration values.
        """
        def replacement_app(environ, start_response):
            cls.install(environ, **settings)
            return app(environ, start_response)
        return replacement_app

def make_getter(meth_name):
    def getter(environ):
        if hasattr(environ, 'environ'):
            environ = environ.environ
        ## FIXME: handle case when security context isn't in place?
        return getattr(environ['deliverance.security_context'], meth_name)(environ)
    getter.func_name = meth_name
    return getter

display_logging = make_getter('display_logging')
display_local_files = make_getter('display_local_files')
execute_pyref = make_getter('execute_pyref')

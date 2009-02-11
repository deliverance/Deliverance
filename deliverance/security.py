"""Implements SecurityContext"""

__all__ = ['SecurityContext']

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

    Also if you use ``force_dev_auth=True`` then DevAuth login will
    not be required, and at all times you will be logged in as a dev
    user.
    """

    def __init__(self, execute_pyref=False, display_logging=None,
                 display_local_files=None, edit_local_files=None, 
                 force_dev_auth=False):
        self._execute_pyref = execute_pyref
        self._display_logging = display_logging
        self._display_local_files = display_local_files
        self._edit_local_files = edit_local_files
        self._force_dev_auth = force_dev_auth
    
    @classmethod
    def install(cls, environ, **kw):
        """
        Instantiate the context and put it into the environment
        """
        inst = cls(**kw)
        environ['deliverance.security_context'] = cls(**kw)
        return inst
    
    def display_logging(self, environ):
        """True if it is allowed to display the log to a user"""
        if self._display_logging is not None:
            return self._display_logging
        return self.is_developer_user(environ)

    def display_local_files(self, environ):
        """True if it is allowed to display local files to developers"""
        if self._display_local_files is not None:
            return self._display_local_files
        return self.is_developer_user(environ)

    def execute_pyref(self, environ):
        """True if it is allowed to execute pyref statements"""
        return self._execute_pyref

    def edit_local_files(self, environ):
        if self._edit_local_files is not None:
            return self._edit_local_files
        return self.is_developer_user(environ)

    def is_developer_user(self, environ):
        """
        True if a developer user (with DevAuth) is logged in.
        """
        if hasattr(environ, 'environ'):
            # Actually a request
            environ = environ.environ
        if self._force_dev_auth:
            return True
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
    """Creates a getter for the given method, that works on an environment alone"""
    def getter(environ):
        """Get the security context and call ``.%(name)s`` on it"""
        if hasattr(environ, 'environ'):
            environ = environ.environ
        ## FIXME: handle case when security context isn't in place?
        return getattr(environ['deliverance.security_context'], meth_name)(environ)
    getter.func_name = meth_name
    getter.__doc__ = getter.__doc__ % dict(name=meth_name)
    return getter

display_logging = make_getter('display_logging')
display_local_files = make_getter('display_local_files')
execute_pyref = make_getter('execute_pyref')
edit_local_files = make_getter('edit_local_files')

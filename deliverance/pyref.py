"""
Handles loading modules or files for use with the ``pyfunc`` attribute
in <match>, <theme> or other places with python hooks
"""
from string import Template
import os
import new
from UserDict import DictMixin
from deliverance.exceptions import DeliveranceSyntaxError
from deliverance.util.importstring import simple_import

__all__ = ['PyReference', 'PyArgs']

class DefaultDict(DictMixin):
    """
    A dictionary where all values have a default
    """
    def __init__(self, wrapping, default=''):
        self.wrapping = wrapping
        self.default = default
    def __getitem__(self, key):
        return self.wrapping.get(key, self.default)
    def __setitem__(self, key, value):
        self.wrapping[key] = value
    def __delitem__(self, key):
        if key in self.wrapping:
            del self.wrapping[key]
    def keys(self):
        return self.wrapping.keys()
    def __contains__(self, key):
        return True

class PyReference(object):
    """
    Represents a reference to a Python function that can be called
    """

    def __init__(self, module_name=None, filename=None, function_name=None, default_objs={}, source_location=None):
        self.module_name = module_name
        self.filename = filename
        self.function_name = function_name
        self.default_objs = default_objs
        self.source_location = source_location
        self._modules = {}

    @classmethod
    def parse(cls, s, source_location, default_function=None, default_objs={}):
        s = s.strip()
        module = filename = None
        if s.startswith('file:'):
            filename = s[len('file:'):]
            if ':' in filename:
                filename, func = filename.split(':', 1)
            else:
                func = default_function
        else:
            # A module name
            if ':' in s:
                module, func = s.split(':', 1)
            else:
                module = s
        if func is None:
            raise DeliveranceSyntaxError(
                "You must provide a function name",
                element=s, source_location=source_location)
        if filename:
            full_file = cls.expand_filename(filename, source_location)
            if not os.path.exists(full_file):
                if full_file != filename:
                    raise DeliveranceSyntaxError(
                        "The filename %r (expanded from %r) does not exist"
                        % (full_file, filename),
                        element=s, source_location=source_location)
                else:
                    raise DeliveranceSyntaxError(
                        "The filename %r does not exist" % full_file,
                        element=s, source_location=source_location)
        return cls(module_name=module, file=filename, function=function, source_location=source_location,
                   default_objs=default_objs)

    def __repr__(self):
        args = [repr(str(self))]
        if self.default_objs:
            args.append('default_objs=%r' % self.default_objs)
        if self.source_location:
            args.append('source_location=%r' % self.source_location)
        return '%s.parse(%s)' % (
            self.__class__.__name__, ', '.join(args))

    def __unicode__(self):
        if self.file:
            return 'file:%s:%s' % (self.file, self.function)
        else:
            return '%s:%s' % (self.module, self.function)

    def __str__(self):
        return unicode(self).encode('utf8')

    @property
    def module(self):
        """
        Returns the instantiated module, or a module created from the filename
        """
        if module_name:
            if module_name not in self._modules:
                new_mod = simple_import(self.module_name)
                for name, value in self.default_objs.items():
                    if not hasattr(new_mod, name):
                        setattr(new_mod, name, value)
                self._modules[module_name] = new_mod
            return self._modules[module_name]
        else:
            filename = self.expand_filename(self.filename, self.source_location)
            if filename not in self._modules:
                name = self.pyfile.strip('/').strip('\\')
                name = os.path.splitext(name)[0]
                name = name.replace('\\', '_').replace('/', '_')
                new_mod = new.module(name)
                new_mod.__file__ = filename
                for name, value in self.default_objs.items():
                    if not hasattr(new_mod, name):
                        setattr(new_mod, name, value)
                self._modules[filename] = new_mod
            return self._modules[filename]

    @property
    def function(self):
        """
        Returns the function object
        """
        obj = self.module
        for p in self.function_name.split('.'):
            ## FIXME: better error handling:
            obj = getattr(obj, p)
        return obj
    
    def __call__(self, *args, **kw):
        return self.function(*args, **kw)
    
    @staticmethod
    def expand_filename(filename, source_location=None):
        """
        Expand environmental variables in a filename
        """
        vars = DefautDict(os.environ)
        tmpl = Template(filename)
        try:
            return tmpl.substitute(os.environ)
        except ValueError, e:
            raise DeliveranceSyntaxError(
                "The filename %r contains bad $ substitutions: %s"
                % (filename, e),
                filename, source_location=source_location)

class PyArgs(object):
    """
    Represents pyarg-* arguments
    """
    def __init__(self, dict):
        self.dict = dict
        
    def __nonzero__(self):
        return bool(self.dict)

    def __unicode__(self):
        return ' '.join('pyargs-%s="%s"' % (name, value) 
                        for name, value in sorted(self.dict.items()))

    def __str__(self):
        return unicode(self).encode('utf8')
    
    def __repr__(self):
        return '%s(%r)' % (self.__class__.__name__, self.dict)
    
    @classmethod
    def from_attrib(cls, attrib):
        kw = {}
        for name in attrib:
            if name.startswith('pyarg-'):
                kw[name[len('pyarg-'):]] = value
        return cls(kw)

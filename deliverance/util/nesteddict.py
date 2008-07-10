"""Implements NestedDict"""

from UserDict import DictMixin

class NestedDict(DictMixin):
    """
    A dictionary that dispatches to one of its sub-dictionaries,
    returning whatever the value is for the first dictionary with the
    key.
    """
    def __init__(self, *dicts):
        self.dicts = dicts
    def __getitem__(self, key):
        for d in self.dicts:
            if key in d:
                return d[key]
        raise KeyError(key)
    def keys(self):
        keys = set()
        for d in self.dicts:
            keys.update(d.keys())
        return list(keys)


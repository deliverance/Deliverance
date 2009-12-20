"""Converts filenames to ``file:`` URLs and back again"""
import urllib
import os
import re

__all__ = ['filename_to_url', 'url_to_filename']

drive_re = re.compile('^([a-z]):', re.I)
url_drive_re = re.compile('^([a-z])[|]', re.I)

def filename_to_url(filename):
    """
    Convert a path to a file: URL.  The path will be made absolute.
    """
    filename = os.path.normcase(os.path.abspath(filename))
    url = filename
    if drive_re.match(url):
        url = url[0] + '|' + url[2:]
    url = url.replace(os.path.sep, '/')
    url = url.lstrip('/')
    return 'file:///' + url

def url_to_filename(url):
    """
    Convert a file: URL to a path.
    """
    assert url.startswith('file:'), (
        "You can only turn file: urls into filenames (not %r)" % url)
    filename = url[len('file:'):].lstrip('/')
    filename = urllib.unquote(filename)
    if url_drive_re.match(filename):
        filename = filename[0] + ':' + filename[2:]
    else:
        filename = '/' + filename
    return filename

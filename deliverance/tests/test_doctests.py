
import doctest
from nose.tools import assert_equals

def test_middleware():
    failures, tests = doctest.testfile('test_middleware.txt')
    assert_equals(failures, 0)

def test_pagematch():
    failures, tests = doctest.testfile('test_pagematch.txt')
    assert_equals(failures, 0)

def test_selection():
    failures, tests = doctest.testfile('test_selection.txt')
    assert_equals(failures, 0)

def test_stringmatch():
    failures, tests = doctest.testfile('test_stringmatch.txt')
    assert_equals(failures, 0)

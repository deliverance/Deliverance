import sys
import os
from deliverance import tests

def main(args=None):
    if args is None:
        args = sys.argv[1:]
    # Kind of a crude way to pass info to nose...
    if sys.argv[0].endswith('.wrapped'):
        # A buildout detail
        sys.argv[0] = sys.argv[0][:-len('.wrapped')]
    remove_items = []
    for i in range(len(args)):
        if args[i] == '--test-file':
            tests.select_tests.append(args[i+1])
            remove_items.extend([i, i+1])
        elif args[i].startswith('--test-file='):
            tests.select_tests.append(args[i][len('--test-file='):])
            remove_items.append(i)
    new_args = []
    for i in range(len(args)):
        if i not in remove_items:
            new_args.append(args[i])
    args = new_args
    os.environ.update(dict(
        NOSE_WHERE=os.path.dirname(os.path.dirname(__file__)),
        NOSE_DETAILED_ERRORS='t',
        NOSE_WITH_DOCTEST='t',
        NOSE_DOCTEST_EXTENSION='.txt',
        NOSE_WITH_MISSING_TESTS='t'))
    if tests.select_tests:
        filename = tests.__file__
        if filename.endswith('.pyc'):
            filename = filename[:-1]
        args.append(filename+':test_examples')
        del os.environ['NOSE_WITH_DOCTEST']
    sys.argv[1:] = args
    try:
        import nose; nose.main()
    finally:
        if '-h' in args or '--help' in args:
            print '  --test-file=FILE'
            print ' '*23, 'Restrict XML test files (Deliverance)'

if __name__ == '__main__':
    main()

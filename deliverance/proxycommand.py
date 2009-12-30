#!/usr/bin/env python
"""Implements the ``deliverance-proxy`` command"""
import sys
import os
import optparse
from paste.httpserver import serve
from deliverance.proxy import ProxySet
from deliverance.proxy import ProxySettings

description = """\
Starts up a proxy server using the given rule file.
"""

parser = optparse.OptionParser(
    usage='%prog [OPTIONS] RULE.xml',
    ## FIXME: get from pkg_resources:
    version='0.1',
    description=description,
    )
## FIXME: these should be handled by the settings (or just picked up from devauth):
parser.add_option(
    '--debug',
    action='store_true',
    dest='debug',
    help='Show debugging information about unexpected exceptions in the browser')
parser.add_option(
    '--interactive-debugger',
    action='store_true',
    dest='interactive_debugger',
    help='Use an interactive debugger (note: security hole when done publically; '
    'if interface is not explicitly given it will be set to 127.0.0.1)')
parser.add_option(
    '--profile',
    action='store_true',
    dest='profile',
    help='Use repoze.profile for profiling requests; go to /_dozer/index '
    'to see the results')
parser.add_option(
    '--memory-profile',
    action='store_true',
    dest='memory_profile',
    help='Use a memory profiler; go to /.deliverance/memory-profile to see results')
parser.add_option(
    '--debug-headers',
    action='count',
    dest='debug_headers',
    help='Show (in the console) all the incoming and outgoing headers; '
    'use twice for bodies')
parser.add_option(
    '--garbage-collect',
    action='store_true',
    dest='garbage_collect',
    help='Wrap the application in a middleware that calls gc.collect() '
    'at the end of every request (see #22)')

def run_command(rule_filename, debug=False, interactive_debugger=False, 
                debug_headers=False, profile=False, memory_profile=False,
                garbage_collect=False):
    """Actually runs the command from the parsed arguments"""
    settings = ProxySettings.parse_file(rule_filename)
    app = ReloadingApp(rule_filename, settings)
    if profile:
        try:
            from repoze.profile.profiler import AccumulatingProfileMiddleware
        except ImportError:
            print 'Error: you must manually install repoze.profiler to use --profile'
            sys.exit(1)
        app = AccumulatingProfileMiddleware(
            app,
            log_filename='/tmp/deliverance-proxy-profiling.log',
            discard_first_request=True,
            flush_at_shutdown=True,
            path='/.deliverance/profile')
    if memory_profile:
        try:
            from dozer import Dozer
        except ImportError:
            print 'Error: you must manually install Dozer to use --memory-profile'
            sys.exit(1)
        app = Dozer(app)
    if interactive_debugger:
        from weberror.evalexception import EvalException
        app = EvalException(app, debug=True)
    else:
        from weberror.errormiddleware import ErrorMiddleware
        app = ErrorMiddleware(app, debug=debug)
    if debug_headers:
        from wsgifilter.proxyapp import DebugHeaders
        app = DebugHeaders(app, show_body=debug_headers > 1)
    if garbage_collect:
        from deliverance.garbagecollect import GarbageCollectingMiddleware
        app = GarbageCollectingMiddleware(app)

    print 'To see logging, visit %s/.deliverance/login' % settings.base_url
    print '    after login go to %s/?deliv_log' % settings.base_url
    if profile:
        print 'To see profiling information visit %s/.deliverance/profile' % settings.base_url
    serve(app, host=settings.host, port=settings.port)

class ReloadingApp(object):
    """
    This is a WSGI app that notices when the rule file changes, and
    reloads it in that case.
    """
    def __init__(self, rule_filename, settings):
        self.rule_filename = rule_filename
        self.settings = settings
        self.proxy_set = None
        self.proxy_set_mtime = None
        self.application = None
        # This gives syntax errors earlier:
        self.load_proxy_set(warn=False)
        
    def __call__(self, environ, start_response):
        if (self.proxy_set is None
            or self.proxy_set_mtime < os.path.getmtime(self.rule_filename)):
            self.load_proxy_set()
        return self.application(environ, start_response)

    def load_proxy_set(self, warn=True):
        """Loads or reloads the ProxySet object from the file"""
        if warn:
            print 'Reloading rule file %s' % self.rule_filename
        self.proxy_set = ProxySet.parse_file(self.rule_filename)
        self.proxy_set_mtime = os.path.getmtime(self.rule_filename)
        self.application = self.settings.middleware(self.proxy_set.application)

def main(args=None):
    """Runs the command from ``sys.argv``"""
    if args is None:
        args = sys.argv[1:]
    options, args = parser.parse_args(args)
    if not args:
        parser.error('You must provide a rule file')
    if len(args) > 1:
        parser.error('Only one argument (the rule file) allowed')
    rule_filename = args[0]
    run_command(rule_filename,
                interactive_debugger=options.interactive_debugger,
                debug=options.debug, debug_headers=options.debug_headers,
                profile=options.profile,
                memory_profile=options.memory_profile,
                garbage_collect=options.garbage_collect)

if __name__ == '__main__':
    main()

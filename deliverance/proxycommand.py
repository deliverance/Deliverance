import os
import optparse
import pkg_resources
import sys
from deliverance import proxyapp

my_package = pkg_resources.get_distribution('Deliverance')

pkg_resources.require('Paste')

from paste import httpserver

help = """\
"""

parser = optparse.OptionParser(
    version=str(my_package),
    usage="%%prog [OPTIONS]\n\n%s" % help)
parser.add_option('--new-layout',
                  dest="new_layout",
                  metavar="DEST_DIR",
                  help="Create a self-contained layout for running the proxy server, with a pre-built theme, rules, and configuration file")
parser.add_option('-s', '--serve',
                  help="The interface to serve on (default 0.0.0.0:80)",
                  dest="serve",
                  metavar="HOST",
                  default="0.0.0.0:80")
parser.add_option('-p', '--proxy',
                  help="The host and port to proxy to (default localhost:8080)",
                  dest="proxy",
                  metavar="PROXY_TO",
                  default='localhost:8080')
parser.add_option('--theme',
                  help="The URI of the theme to use",
                  dest="theme")
parser.add_option('--rule',
                  help="The URI of the ruleset to use",
                  dest="rule")
parser.add_option('--transparent',
                  help="Do not rewrite the Host header when passing the request on",
                  action='store_true',
                  dest='transparent')
parser.add_option('--debug',
                  help="Show tracebacks when an error occurs (use twice for fancy/dangerous traceback)",
                  action="count",
                  dest="debug")
parser.add_option('--request-log',
                  help="Show an apache-style log of requests (use twice for more logging)",
                  action="count",
                  dest="request_log",
                  default=0)
parser.add_option('--rewrite',
                  help="Rewrite all headers and links",
                  action="store_true",
                  dest="rewrite")
parser.add_option('--renderer',
                  dest="renderer",
                  help="Select which renderer to use: 'py' or 'xslt'",
                  default='py')

def strip(prefix, string):
    if string.startswith(prefix):
        return string[len(prefix):]
    else:
        return string

def main(args=None):
    if args is None:
        args = sys.argv[1:]
    options, args = parser.parse_args(args)
    if options.new_layout:
        make_new_layout(options.new_layout)
        return
    serve = strip('http://', options.serve)
    if ':' not in serve:
        serve += ':80'
    proxy = strip('http://', options.proxy)
    if ':' not in proxy:
        proxy += ':80'
    if not options.rule or not options.theme:
        if not options.rule:
            op = '--rule'
        else:
            op = '--theme'
        print 'You must provide the %s option' % op
        sys.exit(2)
    debug_headers = options.request_log > 1
    app = proxyapp.ProxyDeliveranceApp(
        theme_uri=options.theme,
        rule_uri=options.rule,
        proxy=proxy,
        transparent=options.transparent,
        debug_headers=debug_headers,
        relocate_content=options.rewrite, 
        renderer=options.renderer)
    if options.request_log:
        from paste.translogger import TransLogger
        app = TransLogger(app)
    if options.debug:
        if options.debug > 1:
            from paste.evalexception.middleware import EvalException
            app = EvalException(app)
        else:
            from paste.exceptions.errormiddleware import ErrorMiddleware
            app = ErrorMiddleware(app, debug=True)
    print 'Serving on http://%s' % serve
    print 'Proxying from http://%s' % proxy
    try:
        httpserver.serve(app, host=serve)
    except KeyboardInterrupt:
        print 'Exiting.'
        sys.exit()
    
def make_new_layout(dest_dir):
    source = os.path.join(os.path.dirname(__file__), 'new_layout_template')
    from paste.script import copydir
    copydir.copy_dir(
        source, dest_dir, {}, 1, simulate=False, interactive=True,
        svn_add=False)


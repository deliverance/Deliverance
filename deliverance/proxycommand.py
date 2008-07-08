import sys
import os
import optparse
from deliverance.proxy import ProxySet
from deliverance.proxy import ProxySettings

from lxml.etree import parse
from paste.httpserver import serve
import urllib

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

def run_command(rule_filename, debug=False, interactive_debugger=False):
    rule_url = 'file://' + urllib.quote(os.path.abspath(rule_filename).replace(os.path.sep, '/'))
    el = parse(rule_filename, base_url=rule_url).getroot()
    ## FIXME: rule_filename isn't browsable in the logs
    ps = ProxySet.parse_xml(el, rule_url)
    settings = ProxySettings.parse_xml(el, rule_url, traverse=True)
    app = ps.application
    app = settings.middleware(app)
    if interactive_debugger:
        from weberror.evalexception import EvalException
        app = EvalException(app, debug=True)
    else:
        from weberror.errormiddleware import ErrorMiddleware
        app = ErrorMiddleware(app, debug=debug)
    print 'To see logging, visit %s/.deliverance/login' % settings.base_url
    serve(app, host=settings.host, port=settings.port)

def main(args=None):
    if args is None:
        args = sys.argv[1:]
    options, args = parser.parse_args()
    if not args:
        parser.error('You must provide a rule file')
    if len(args) > 1:
        parser.error('Only one argument (the rule file) allowed')
    rule_filename = args[0]
    run_command(rule_filename,
                interactive_debugger=options.interactive_debugger,
                debug=options.debug)

if __name__ == '__main__':
    main()

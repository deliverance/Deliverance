"""
Experimental proxy command using WSGIFilter
"""

import sys
import pkg_resources
pkg_resources.require('WSGIFilter')
from wsgifilter.proxycommand import *
from deliverance.wsgimiddleware import DeliveranceMiddleware

def make_middleware_factory(theme_uri, rule_uri, renderer='py'):
    def make_middleware(app):
        return DeliveranceMiddleware(
            app, theme_uri=theme_uri, rule_uri=rule_uri,
            renderer=renderer)
    return make_middleware

def main(args=None):
    if args is None:
        args = sys.argv[1:]
    parser = make_basic_optparser(
        'Deliverance')
    parser.add_option(
        '--theme',
        help="The URI of the theme to use",
        dest="theme_uri")
    parser.add_option(
        '--rule',
        help="The URI of the ruleset to use",
        dest="rule_uri")
    parser.add_option(
        '--renderer',
        help="Select which renderer to use: 'py' or 'xslt'",
        default='py')
    options, args = parser.parse_args(args)
    middleware = make_middleware_factory(
        theme_uri=options.theme_uri,
        rule_uri=options.rule_uri,
        renderer=options.renderer)
    run_proxy_command(
        options, args, middleware, parser)
    
if __name__ == '__main__':
    import pkg_resources
    pkg_resources.require('Deliverance')
    from deliverance.exp_proxycommand import main as exp_main
    exp_main()
    

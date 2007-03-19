"""
This module contains the commands used in deliverance file layouts,
where you have a deliverance-proxy-run and deliverance-proxy-ctl
commands bound a specific configuration.
"""

import os
import sys
from paste.script import serve
from paste.script import exe

def proxy_run(script_filename):
    """
    Using script_filename, this determines the configuration and executes
    ``paster serve``
    """
    config_filename = find_config(script_filename)
    cmd = serve.ServeCommand('serve')
    cmd.run([config_filename] + sys.argv[1:])
    
def proxy_ctl(script_filename):
    """
    Using script_filename, this determines the configuration and executes
    ``paster serve --daemon`` plus the given commands
    """
    config_filename = find_config(script_filename)
    os.environ['_'] = config_filename
    cmd = exe.ExeCommand('exe')
    cmd.run([config_filename] + sys.argv[1:])

def find_config(script_filename):
    return os.path.join(
        os.path.dirname(os.path.dirname(script_filename)),
        'etc', 'deliverance-proxy.ini')

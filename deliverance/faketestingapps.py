"""
These applications are intended for load testing odd situations with
Deliverance.  Two models are implemented:

* Slow servers
* Random content

Both support probabilities (e.g., return random content on some
probability, or slow down a certain percentage of requests).
"""
import random
import time

__all__ = ['Switcher']

class Switcher(object):

    """
    Switches request paths.

    Usage::

        [filter-app:switchedapp]
        paste.filter_app_factory = deliverance.faketestingapps.Switcher
        /bad_content.html = 10
        next = static

        [app:static]
        use = egg:Paste#static
        document_root = /some/dir

    Then 90% of the time / will direct to /some/dir/index.html (the
    default) and 10% of the time to /some/dir/bad_content.html.
    """

    def __init__(self, app, global_conf, **paths):
        self.app = app
        self.redirects = []
        total_prob = 0
        for path, prob in paths.items():
            if not path.startswith('/'):
                path = '/'+path
            prob = float(prob) / 100.0
            total_prob += prob
            self.redirects.append((path, prob))

    def __call__(self, environ, start_response):
        prob = random.random()
        for path, path_prob in self.redirects:
            if prob < path_prob:
                environ['PATH_INFO'] = path
                break
        return self.app(environ, start_response)


class Pauser(object):

    """
    Pauses some requests.

    Usage::

        [filter-app:pauser]
        paste.filter_app_factory = deliverance.faketestingapps.Pauser
        # 10% of the time:
        probability = 10
        # pause 5 seconds:
        pause = 5
        next = static

        [app:static]
        use = egg:Paste#static
        document_root = /docroot
    """

    def __init__(self, app, global_conf, probability, pause):
        self.app = app
        self.probability = float(probability)
        self.pause = float(pause)

    def __call__(self, environ, start_response):
        if random.random()*100 < self.probability:
            time.sleep(self.pause)
        return self.app(environ, start_response)
    

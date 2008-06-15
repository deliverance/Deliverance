__version__ = '0.1.99.simplon.1'

from setuptools import setup, find_packages

setup(name="Deliverance",
      version=__version__,
      description="Deliverance rewrites HTML to add theming",
      long_description="""\
Deliverance rewrites HTML pages to theme the pages -- adding things
like navigation, stylesheets, and applying a common look-and-feel to
content from a variety of sources.

Unlike typical templating systems, Deliverance works only on HTML;
there's no variables to substitute or Python structures involved.  It
takes a simple set of rules and applies these to the HTML, so you can
style the output of pages regardless of where the page comes from.

The theme itself is an HTML page with zero code in it.  It is simply
an example of what a page should look like; this makes it accessible
to designers or any kind of tool, and may itself even be dynamically
generated.  For instance, you might use a blog page as a theme, and
wrap that theme around a wiki to give the two a common look and feel.

The rules are written in an XML format, that looks something like::

  <rules xmlns:xi="http://www.w3.org/2001/XInclude"
         xmlns="http://www.plone.org/deliverance" >
    <xi:include href="standardrules.xml" />
    <copy theme="//div[@id='container']"
          content="//*[@id='portal-columns']" />
  </rules>

This example, in addition to doing the 'standard' things (which
includes merging the ``<head>`` of both pages) also copies the tag
``<div id="portal-columns">`` into the theme page's
``<div id="container">``.

Deliverance is implemented as both a rendering object and WSGI
middleware.  Included in the package is a script that uses the WSGI
middleware as an HTTP proxy.
""",
      classifiers=[
          'Development Status :: 4 - Beta',
          'Intended Audience :: Developers',
          'Topic :: Internet :: WWW/HTTP',
          'Topic :: Internet :: WWW/HTTP :: WSGI',
          'Topic :: Internet :: WWW/HTTP :: WSGI :: Middleware',
          ],
      keywords='templating html web wsgi middleware http proxy',
      author="Deliverance Developer Community",
      author_email="deliverance-devel@lists.openplans.org",
      url="http://openplans.org/projects/deliverance",
      license="",
      packages=find_packages(exclude=[]),
      zip_safe=False,
      install_requires=[
        'lxml>=1.2',
        'Paste',
	'FormEncode',
	'elementtree',
	'nose',
	'WSGIFilter',
	'setuptools'
      ],
      include_package_data=True,
      entry_points="""
      [paste.filter_app_factory]
      main = deliverance.wsgimiddleware:make_filter

      [paste.app_factory]
      proxy = deliverance.proxyapp:make_proxy

      [console_scripts]
      deliverance-proxy = deliverance.proxycommand:main
      deliverance-tests = deliverance.testrunner:main
      deliverance-speed = deliverance.test_speed:main
      deliverance-handtransform = deliverance.handtransform:main
      deliverance-static = deliverance.staticcommand:main
      """,
      tests_require=[ 
          'nose', 
          ], 
      test_suite='nose.collector', 
      )



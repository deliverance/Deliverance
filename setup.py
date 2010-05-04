from setuptools import setup, find_packages

version = '0.3c4'

setup(name='Deliverance',
      version=version,
      description="Deliverance transforms HTML to theme pages",
      long_description="""\
Deliverance does transformations of HTML to 'theme' pages, similar in
function to XSLT but using a simpler XML-based language to express the
transformation.

New in this release:

%s
""" % open('changes_on_trunk.txt').read(),
      classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Web Environment",
        "License :: OSI Approved :: MIT License",
        "Topic :: Internet :: WWW/HTTP :: WSGI",
        "Topic :: Internet :: WWW/HTTP :: WSGI :: Middleware",
      ],
      keywords='wsgi theming html',
      author='Ian Bicking, The Open Planning Project, and the Deliverance development community',
      author_email='deliverance-devel@lists.coactivate.org',
      url='http://deliverance.openplans.org/',
      license='MIT',
      packages=find_packages(exclude=['ez_setup', 'examples', 'tests']),
      include_package_data=True,
      zip_safe=False,
      test_suite='nose.collector', 
      tests_require=['nose'],
      install_requires=[
        "lxml>=2.1alpha1",
        "WebOb",
        "WSGIProxy",
        "Tempita",
        "Pygments",
        "WebError",
        "DevAuth",
        "Paste",
        "PasteScript",
        "WSGIFilter",
        "chardet",
        "simplejson",
        ],
      dependency_links=[
        "https://svn.openplans.org/svn/DevAuth/trunk#egg=DevAuth-dev",
        ],
      entry_points="""
      [console_scripts]
      deliverance-proxy = deliverance.proxycommand:main

      [paste.paster_create_template]
      deliverance = deliverance.paster_templates:DeliveranceTemplate
      deliverance_plone = deliverance.paster_templates:PloneTemplate

      [paste.filter_app_factory]
      main = deliverance.middleware:make_deliverance_middleware

      [paste.filter_factory]
      garbagecollect = deliverance.garbagecollect:filter_factory
      """,
      )

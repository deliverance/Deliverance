from setuptools import setup, find_packages

version = '0.5.0'

setup(name='Deliverance',
      version=version,
      description="Deliverance transforms HTML to theme pages",
      long_description="""\
Deliverance does transformations of HTML to 'theme' pages, similar in
function to XSLT but using a simpler XML-based language to express the
transformation.
""",
      classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Web Environment",
        "License :: OSI Approved :: MIT License",
        "Topic :: Internet :: WWW/HTTP :: WSGI",
        "Topic :: Internet :: WWW/HTTP :: WSGI :: Middleware",
      ],
      keywords='wsgi theming html',
      author='Ian Bicking, Ethan Jucovy',
      author_email='deliverance-devel@lists.coactivate.org',
      url='https://github.com/deliverance/Deliverance/',
      license='MIT',
      packages=find_packages(exclude=['ez_setup', 'examples', 'tests']),
      include_package_data=True,
      zip_safe=False,
      test_suite='nose.collector', 
      tests_require=['nose', "WebTest"],
      install_requires=[
        "lxml",
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

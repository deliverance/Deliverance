from setuptools import setup, find_packages
import sys, os

version = '0.2'

setup(name='deliverance',
      version=version,
      description="",
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
      author='Ian Bicking, The Open Planning Project',
      author_email='deliverance-discuss@lists.openplans.org',
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
        "WSGIFilter",
        ],
      dependency_links=[
        "https://svn.openplans.org/svn/DevAuth/trunk#egg=DevAuth-dev",
        ],
      entry_points="""
      [console_scripts]
      deliverance-proxy = deliverance.proxycommand:main
      """,
      )

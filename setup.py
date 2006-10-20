__version__ = '0.1'

from setuptools import setup, find_packages

setup(name="Deliverance",
      version=__version__,
      description="",
      long_description="""\
""",
      classifiers=[
        # dev status, license, HTTP categories
        ],
      keywords='',
      author="Paul Everitt",
      author_email="",
      url="",
      license="",
      packages=find_packages(exclude=[]),
      zip_safe=False,
      install_requires=[
        'lxml',
        'paste==dev,>=0.9.9a'
      ],
      include_package_data=True,
      entry_points="""
      [paste.filter_app_factory]
      main = deliverance.wsgifilter:make_filter

      [console_scripts]
      deliverance-proxy = deliverance.proxycommand:main
      """,
      )



from setuptools import setup, find_packages
import sys, os

version = '0.2'

setup(name='deliverance',
      version=version,
      description="",
      long_description="""\
""",
      classifiers=[], # Get strings from http://pypi.python.org/pypi?%3Aaction=list_classifiers
      keywords='',
      author='',
      author_email='',
      url='http://openplans.org/projects/deliverance/',
      license='MIT',
      packages=find_packages(exclude=['ez_setup', 'examples', 'tests']),
      include_package_data=True,
      zip_safe=False,
      install_requires=[
        "lxml",
      ],
      entry_points="""
      # -*- Entry points: -*-
      """,
      )

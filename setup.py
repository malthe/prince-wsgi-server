import os

from setuptools import setup, find_packages

setup(name='Prince',
      version='1.1',
      classifiers=[
        "Programming Language :: Python",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Internet :: WWW/HTTP :: WSGI :: Application",
        ],
      author='Malthe Borch',
      author_email='mborch@gmail.com',
      url='',
      packages=find_packages('src'),
      package_dir = {'': 'src'},
      include_package_data=True,
      zip_safe=False,
      install_requires=[
            'WebOb',
            ],
      entry_points = """\
      [paste.app_factory]
      app = prince.app:make_app
      """
      )

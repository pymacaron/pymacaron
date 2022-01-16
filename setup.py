from setuptools import setup
import sys
import os
from os import path
from glob import glob

version = None

if sys.argv[-2] == '--version' and 'sdist' in sys.argv:
    version = sys.argv[-1]
    sys.argv.pop()
    sys.argv.pop()

if 'sdist' in sys.argv and not version:
    raise Exception("Please set a version with --version x.y.z")

if not version:
    if 'sdist' in sys.argv:
        raise Exception("Please set a version with --version x.y.z")
    else:
        path_pkg_info = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'PKG-INFO')
        if os.path.isfile(path_pkg_info):
            with open(path_pkg_info, 'r')as f:
                for line in f.readlines():
                    if 'Version' in line:
                        _, version = line.split(' ')
        else:
            print("WARNING: cannot set version in custom setup.py")

if version:
    version = version.strip()
print("version: %s" % version)

# read the contents of the README file
this_directory = path.abspath(path.dirname(__file__))
with open(path.join(this_directory, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='pymacaron',
    version=version,
    url='https://github.com/pymacaron/pymacaron',
    license='BSD',
    author='Erwan Lemonnier',
    author_email='erwan@lemonnier.se',
    description='REST microservice framework based on Flask, OpenAPI, gunicorn and celery, deployable towards GKE and Beanstalk',
    long_description=long_description,
    long_description_content_type='text/markdown',
    python_requires='>=3.8',
    install_requires=[
        'pymacaron-unit>=1.0.10',
        'pymacaron-core>=1.0.146',
        'flask>=1.0.4',
        'flask-cors',
        'flask-compress',
        'Werkzeug==0.16.0',
        'click',
        'pytz',
        'PyJWT',
        'PyYAML>=5.1.2',
    ],
    tests_require=[
        'psutil',
        'nose',
        'mock',
        'pycodestyle'
        'pymacaron-unit>=1.0.10',
        'pymacaron-core>=1.0.146',
        'flask>=1.0.4',
        'flask-cors',
        'flask-compress',
        'click',
        'pytz',
        'PyJWT',
        'PyYAML>=5.1.2',
    ],
    packages=['pymacaron'],
    package_data={'pymacaron': ['*.yaml']},
    scripts=glob("bin/*"),
    test_suite='nose.collector',
    zip_safe=False,
    platforms='any',
    classifiers=[
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'Topic :: Software Development :: Libraries :: Python Modules'
    ]
)

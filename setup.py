#!/usr/bin/env python
import os
from setuptools import setup


def _read(fname):
    try:
        return open(os.path.join(os.path.dirname(__file__), fname)).read()
    except IOError:
        return ''


REQUIREMENTS = [l for l in _read('requirements.txt').split('\n') if l and not l.startswith('#')]
VERSION = '2.0.1'

setup(
        name='bottle-swagger-2',
        version=VERSION,
        url='https://github.com/cope-systems/bottle-swagger',
        download_url='https://github.com/cope-systems/bottle-swaggerr/archive/v{}.tar.gz'.format(VERSION),
        description='Swagger Integration for Bottle',
        long_description="""
        bottle-swagger-2 is a revamped Swagger 2.0/Bravado integration for the Bottle web framework.
        """.strip(),
        author='Robert Cope, Charles Blaxland',
        author_email='robert@copesystems.com, charles.blaxland@gmail.com',
        license='MIT',
        platforms='any',
        packages=["bottle_swagger"],
        package_data={"bottle_swagger": ["*.png", "*.html", "*.html.st", "*.css", "*.js"]},
        # setup_requires=['sphinx', 'sphinx_rtd_theme'],
        install_requires=REQUIREMENTS,
        tests_require=REQUIREMENTS + ["tox", "webtest"],
        classifiers=[
            'Environment :: Web Environment',
            'Environment :: Plugins',
            'Framework :: Bottle',
            'Intended Audience :: Developers',
            'License :: OSI Approved :: MIT License',
            'Operating System :: OS Independent',
            'Programming Language :: Python',
            'Programming Language :: Python :: 2.7',
            'Programming Language :: Python :: 3.4',
            'Programming Language :: Python :: 3.5',
            'Programming Language :: Python :: 3.6',
            'Programming Language :: Python :: 3.7',
            'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
            'Topic :: Software Development :: Libraries :: Python Modules'
        ],
        include_package_data=True
)

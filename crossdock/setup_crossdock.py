#!/usr/bin/env python
# -*- coding: utf-8 -*-

from setuptools import setup, find_packages

version = '1.0.1'

with open('crossdock/version.py', 'w') as fp:
    fp.write("__version__ = '%s'\n" % version)

setup(
    name='crossdock',
    version=version,
    include_package_data=True,
    zip_safe=False,
    packages=find_packages(exclude=['tests', 'example', 'tests.*']),
    entry_points={
        'console_scripts': [
            'crossdock = crossdock.server.server:serve',
        ]
    },
    install_requires=[
        'tchannel>=0.24,<0.27',
        'opentracing_instrumentation>=2,<3',
    ],
)

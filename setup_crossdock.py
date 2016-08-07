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
        'tchannel<0.25',
        # 'git://github.com/uber-common/opentracing-python-instrumentation
        # .git@upgrade-to-span-context#egg=opentracing_instrumentation',
        'opentracing_instrumentation==2.0.0.dev3',
    ],
)

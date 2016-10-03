#!/usr/bin/env python
# -*- coding: utf-8 -*-
import re

from setuptools import setup, find_packages

version = None
with open('jaeger_client/__init__.py', 'r') as f:
    for line in f:
        m = re.match(r'^__version__\s*=\s*(["\'])([^"\']+)\1', line)
        if m:
            version = m.group(2)
            break

assert version is not None, \
    'Could not determine version number from jaeger_client/__init__.py'

setup(
    name='jaeger-client',
    version=version,
    url='https://github.com/uber/jaeger-client-python',
    description='Jaeger Python OpenTracing Tracer implementation',
    author='Yuri Shkuro',
    author_email='ys@uber.com',
    packages=find_packages(exclude=['crossdock', 'tests', 'example', 'tests.*']),
    include_package_data=True,
    license="MIT",
    zip_safe=False,
    keywords='jaeger, tracing, opentracing',
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Programming Language :: Python :: 2.7',
    ],
    install_requires=[
        'futures',
        'threadloop>=1,<2',
        # we want thrift>=0.9.2.post1,<0.9.3, but we let the users pin to that
        'thrift',
        'tornado>=4.3,<5',
        'opentracing>=1.2.2,<1.3',
    ],
    # Uncomment below if need to test with unreleased version of opentracing
    # dependency_links=[
    #     'git+ssh://git@github.com/opentracing/opentracing-python.git@BRANCHNAME#egg=opentracing',
    # ],
    test_suite='tests',
    extras_require={
        'tests': [
            'mock==1.0.1',
            'pytest>=2.7,<3',
            'pytest-cov',
            'pytest-timeout',
            'pytest-tornado',
            'pytest-benchmark[histogram]>=3.0.0rc1',
            'flake8<3',  # see https://github.com/zheller/flake8-quotes/issues/29
            'flake8-quotes',
            'coveralls',
            'tchannel>=0.27',
            'opentracing_instrumentation>=2,<3',
        ]
    },
)

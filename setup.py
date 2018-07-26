#!/usr/bin/env python
# -*- coding: utf-8 -*-
import re
import os
from setuptools import setup, find_packages

version = None
with open('jaeger_client/__init__.py', 'r') as f:
    for line in f:
        m = re.match(r'^__version__\s*=\s*(["\'])([^"\']+)\1', line)
        if m:
            version = m.group(2)
            break
# This is because thrift for python doesn't have 'package_prefix'.
# The thrift compiled libraries refer to each other relative to their subdir.
for dname, dirs, files in os.walk("jaeger_client/thrift_gen/agent"):
    for fname in files:
        fpath = os.path.join(dname, fname)
        with open(fpath) as f:
            s = f.read()
        if "jaeger_client.thrift_gen.jaeger" not in s:
            s = s.replace("jaeger", 'jaeger_client.thrift_gen.jaeger')
            s = s.replace('zipkincore', 'jaeger_client.thrift_gen.zipkincore')
            with open(fpath, "w") as f:
                f.write(s)

with open('jaeger_client/thrift_gen/jaeger/__init__.py', 'r') as f:
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
    url='https://github.com/jaegertracing/jaeger-client-python',
    description='Jaeger Python OpenTracing Tracer implementation',
    author='Yuri Shkuro',
    author_email='ys@uber.com',
    packages=find_packages(exclude=['crossdock', 'tests', 'example', 'tests.*']),
    include_package_data=True,
    license='Apache License 2.0',
    zip_safe=False,
    keywords='jaeger, tracing, opentracing',
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Natural Language :: English',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.6',
    ],
    install_requires=[
        'threadloop>=1,<2',
        'thrift',
        'tornado>=4.3,<5',
        'opentracing>=1.2.2,<2',
    ],
    # Uncomment below if need to test with unreleased version of opentracing
    # dependency_links=[
    #     'git+ssh://git@github.com/opentracing/opentracing-python.git@BRANCHNAME#egg=opentracing',
    # ],
    test_suite='tests',
    extras_require={
        'tests': [
            'mock==1.0.1',
            'pycurl>=7.43,<8',
            'pytest>=2.7,<3',
            'pytest-cov',
            'coverage<4.4',  # can remove after https://bitbucket.org/ned/coveragepy/issues/581/44b1-44-breaking-in-ci
            'pytest-timeout',
            'pytest-tornado',
            'pytest-benchmark[histogram]>=3.0.0rc1',
            'pytest-localserver',
            'flake8<3',  # see https://github.com/zheller/flake8-quotes/issues/29
            'flake8-quotes',
            'coveralls',
            'tchannel>=0.27',  # This is only used in python 2
            'opentracing_instrumentation>=2,<3',
            'prometheus_client',
        ]
    },
)

#!/usr/bin/env python
# -*- coding: utf-8 -*-

from setuptools import setup, find_packages

version = '2.0.0.dev0'

with open('jaeger_client/version.py', 'w') as fp:
    fp.write("__version__ = '%s'\n" % version)

setup(
    name='jaeger-client',
    version=version,
    url='https://github.com/uber/jaeger-client-python',
    description='Jaeger Python OpenTracing Tracer implementation',
    author='Yuri Shkuro',
    author_email='ys@uber.com',
    packages=find_packages(exclude=['tests', 'example', 'tests.*']),
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
        'opentracing==2.0.0.dev1',
<<<<<<< 50ec20e6f24e85d7c14e09a5d9ddfaf7d59e82b7
        'tchannel>=0.24,<1.0',  # TODO this should be removed
        'opentracing_instrumentation==2.0.0.dev1',  # TODO only used to init headers config, should be removed
=======
        'opentracing_instrumentation==2.0.0.dev1',  # TODO should be removed and used from setup libs
>>>>>>> Remove tchannel
    ],
    test_suite='tests',
    extras_require={
        'tests': [
            'mock==1.0.1',
            'pytest>=2.7,<3',
            'pytest-cov',
            'pytest-timeout',
            'pytest-tornado',
            'pytest-benchmark[histogram]>=3.0.0rc1',
            'flake8==2.1.0',
            'coveralls',
        ]
    },
)

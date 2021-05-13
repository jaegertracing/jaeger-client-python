# Copyright (c) 2016 Uber Technologies, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# !/usr/bin/env python
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
        'tchannel==2.1.0'
    ],
)

from __future__ import absolute_import

# This is because thrift for python doesn't have 'package_prefix'.
# The thrift compiled libraries refer to each other relative to their subdir.
import crossdock.thrift_gen as modpath
import sys
sys.path.append(modpath.__path__[0])

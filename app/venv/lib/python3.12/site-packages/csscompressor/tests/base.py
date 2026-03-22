##
# Copyright (c) 2013 Sprymix Inc.
# All rights reserved.
#
# See LICENSE for details.
##


from csscompressor import compress

import unittest


class BaseTest(unittest.TestCase):
    def _test(self, input, output):
        result = compress(input)
        if result != output.strip():
            print()
            print('CSM', repr(result))
            print()
            print('YUI', repr(output))
            print()

            # import difflib
            # d = difflib.Differ()
            # diff = list(d.compare(result, output.strip()))
            # from pprint import pprint
            # pprint(diff)

            assert False

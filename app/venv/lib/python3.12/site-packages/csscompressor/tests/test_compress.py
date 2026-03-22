##
# Copyright (c) 2013 Sprymix Inc.
# All rights reserved.
#
# See LICENSE for details.
##


from csscompressor.tests.base import BaseTest
from csscompressor import compress

import unittest


class Tests(unittest.TestCase):
    def test_linelen_1(self):
        input = '''
            a {content: '}}'}
            b {content: '}'}
            c {content: '{'}
        '''
        output = compress(input, max_linelen=2)
        assert output == "a{content:'}}'}\nb{content:'}'}\nc{content:'{'}"

    def test_linelen_2(self):
        input = ''
        output = compress(input, max_linelen=2)
        assert output == ""

    def test_linelen_3(self):
        input = '''
            a {content: '}}'}
            b {content: '}'}
            c {content: '{'}
            d {content: '{'}
        '''
        output = compress(input, max_linelen=100)
        assert output == "a{content:'}}'}b{content:'}'}c{content:'{'}\nd{content:'{'}"

    def test_compress_1(self):
        input = '''
            a {content: '}}'} /*
            b {content: '}'}
            c {content: '{'}
            d {content: '{'}
        '''
        output = compress(input)
        assert output == "a{content:'}}'}"

    def test_compress_2(self):
        input = '''
            a {content: calc(10px-10%}
        '''
        self.assertRaises(ValueError, compress, input)

    def test_nested_1(self):
        input = '''
            a { width: calc( (10vh - 100px) / 4 + 30px ) }
        '''
        output = compress(input)
        assert output == "a{width:calc((10vh - 100px) / 4 + 30px)}"

    def test_nested_2(self):
        input = '''
            a { width: calc( ((10vh - 100px) / 4 + 30px ) }
        '''
        self.assertRaises(ValueError, compress, input)

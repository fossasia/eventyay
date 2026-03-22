##
# Copyright (c) 2013 Sprymix Inc.
# All rights reserved.
#
# See LICENSE for details.
##


from csscompressor.tests.base import BaseTest
from csscompressor import compress_partitioned

import unittest


class Tests(unittest.TestCase):
    def test_partition_1(self):
        input = ''
        output = compress_partitioned(input, max_rules_per_file=2)
        assert output == ['']

    def test_partition_2(self):
        input = '''
            a {content: '}}'}
            b {content: '}'}
            c {content: '{'}
        '''

        output = compress_partitioned(input, max_rules_per_file=2)
        assert output == ["a{content:'}}'}b{content:'}'}", "c{content:'{'}"]

    def test_partition_3(self):
        input = '''
            @media{
                a {p: 1}
                b {p: 2}
                x {p: 2}
            }
            @media{
                c {p: 1}
                d {p: 2}
                y {p: 2}
            }
            @media{
                e {p: 1}
                f {p: 2}
                z {p: 2}
            }
        '''

        output = compress_partitioned(input, max_rules_per_file=2)
        assert output == ['@media{a{p:1}b{p:2}x{p:2}}',
                          '@media{c{p:1}d{p:2}y{p:2}}',
                          '@media{e{p:1}f{p:2}z{p:2}}']

    def test_partition_4(self):
        input = '''
            @media{
                a {p: 1}
                b {p: 2}
                x {p: 2}
        '''

        self.assertRaises(ValueError, compress_partitioned,
                          input, max_rules_per_file=2)

    def test_partition_5(self):
        input = '''
            @media{
                a {p: 1}
                b {p: 2}
                x {p: 2}

            @media{
                c {p: 1}
                d {p: 2}
                y {p: 2}
            }
            @media{
                e {p: 1}
                f {p: 2}
                z {p: 2}
            }
        '''

        self.assertRaises(ValueError, compress_partitioned,
                          input, max_rules_per_file=2)

    def test_partition_6(self):
        input = '''
            @media{}}

                a {p: 1}
                b {p: 2}
                x {p: 2}
        '''

        self.assertRaises(ValueError, compress_partitioned,
                          input, max_rules_per_file=2)

    def test_partition_7(self):
        input = '''
            a, a1, a2 {color: red}
            b, b2, b3 {color: red}
            c, c3, c4, c5 {color: red}
            d {color: red}
        '''

        output = compress_partitioned(input, max_rules_per_file=2)
        assert output == ['a,a1,a2{color:red}', 'b,b2,b3{color:red}',
                          'c,c3,c4,c5{color:red}', 'd{color:red}']

    def test_partition_8(self):
        input = '''
            @media{
                a {p: 1}
                b {p: 2}
                x {p: 2}
            }
            @media{
                c {p: 1}
                d {p: 2}
                y {p: 2}
            }
            @media{
                e {p: 1}
                f {p: 2}
                z {p: 2}
            }
            z {p: 2}
        '''

        # carefully pick 'max_linelen' to have a trailing '\n' after
        # '_compress' call
        output = compress_partitioned(input, max_rules_per_file=2, max_linelen=6)
        assert output == ['@media{a{p:1}\nb{p:2}x{p:2}\n}',
                          '@media{c{p:1}\nd{p:2}y{p:2}\n}',
                          '@media{e{p:1}\nf{p:2}z{p:2}\n}',
                          'z{p:2}']

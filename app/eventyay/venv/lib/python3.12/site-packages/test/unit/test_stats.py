# -*- coding: utf-8 -*-
import json
from sendgrid.helpers.stats import *

try:
    import unittest2 as unittest
except ImportError:
    import unittest


class UnitTests(unittest.TestCase):

    def test_basicStats(self):

        """Minimum required for stats"""
        global_stats = Stats(start_date='12-09-2017')

        self.assertEqual(
            json.dumps(
                global_stats.get(),
                sort_keys=True),
            '{"start_date": "12-09-2017"}'
        )

        self.assertTrue(isinstance(str(global_stats), str))

    def test_Stats(self):

        all_stats = Stats(start_date='12-09-2017')
        all_stats.end_date = '12-10-2017'
        all_stats.aggregated_by = 'day'
        all_stats._sort_by_direction = 'asc'
        all_stats.sort_by_metric = 'clicks'
        all_stats._limit = 100
        all_stats._offset = 2

        self.assertEqual(
            json.dumps(
                all_stats.get(),
                sort_keys=True),
            '{"aggregated_by": "day", "end_date": "12-10-2017", '
            '"limit": 100, "offset": 2, "sort_by_direction": "asc", '
            '"sort_by_metric": "clicks", "start_date": "12-09-2017"}'
        )

    def test_categoryStats(self):

        category_stats = CategoryStats(start_date='12-09-2017', categories=['foo', 'bar'])
        category_stats.add_category(Category('woo'))
        category_stats.end_date = '12-10-2017'
        category_stats.aggregated_by = 'day'
        category_stats._sort_by_direction = 'asc'
        category_stats.sort_by_metric = 'clicks'
        category_stats._limit = 100
        category_stats._offset = 2

        self.assertEqual(
            json.dumps(
                category_stats.get(),
                sort_keys=True),
            '{"aggregated_by": "day", "categories": ["foo", "bar", "woo"], '
            '"end_date": "12-10-2017", "limit": 100, "offset": 2, '
            '"sort_by_direction": "asc", "sort_by_metric": "clicks", '
            '"start_date": "12-09-2017"}'
        )

    def test_subuserStats(self):

        subuser_stats = SubuserStats(start_date = '12-09-2017', subusers=['foo', 'bar'])
        subuser_stats.add_subuser(Subuser('blah'))
        subuser_stats.end_date = '12-10-2017'
        subuser_stats.aggregated_by = 'day'
        subuser_stats._sort_by_direction = 'asc'
        subuser_stats.sort_by_metric = 'clicks'
        subuser_stats._limit = 100
        subuser_stats._offset = 2

        self.assertEqual(
            json.dumps(
                subuser_stats.get(),
                sort_keys=True),
            '{"aggregated_by": "day", "end_date": "12-10-2017", '
            '"limit": 100, "offset": 2, "sort_by_direction": "asc", '
            '"sort_by_metric": "clicks", "start_date": "12-09-2017", '
            '"subusers": ["foo", "bar", "blah"]}'
        )

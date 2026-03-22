from sendgrid.helpers.mail.spam_check import SpamCheck

try:
    import unittest2 as unittest
except ImportError:
    import unittest


class UnitTests(unittest.TestCase):

    def test_spam_all_values(self):
        expected = {'enable': True, 'threshold': 5, 'post_to_url': 'https://www.test.com'}
        spam_check = SpamCheck(enable=True, threshold=5, post_to_url='https://www.test.com')
        self.assertEqual(spam_check.get(), expected)

    def test_spam_no_url(self):
        expected = {'enable': True, 'threshold': 10}
        spam_check = SpamCheck(enable=True, threshold=10)
        self.assertEqual(spam_check.get(), expected)

    def test_spam_no_threshold(self):
        expected = {'enable': True}
        spam_check = SpamCheck(enable=True)
        self.assertEqual(spam_check.get(), expected)

    def test_has_values_but_not_enabled(self):
        expected = {'enable': False, 'threshold': 1, 'post_to_url': 'https://www.test.com'}
        spam_check = SpamCheck(enable=False, threshold=1, post_to_url='https://www.test.com')
        self.assertEqual(spam_check.get(), expected)

    def test_spam_change_properties(self):
        """Tests changing the properties of the spam check class"""
        expected = {'enable': False, 'threshold': 10, 'post_to_url': 'https://www.testing.com'}
        spam_check = SpamCheck(enable=True, threshold=5, post_to_url='https://www.test.com')
        spam_check.enable = False
        spam_check.threshold = 10
        spam_check.post_to_url = 'https://www.testing.com'
        self.assertEqual(spam_check.get(), expected)

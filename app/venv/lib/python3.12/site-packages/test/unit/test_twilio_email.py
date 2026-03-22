import os
import unittest

from sendgrid import TwilioEmailAPIClient


class UnitTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        os.environ['TWILIO_API_KEY'] = 'api-key'
        os.environ['TWILIO_API_SECRET'] = 'api-secret'
        os.environ['TWILIO_ACCOUNT_SID'] = 'account-sid'
        os.environ['TWILIO_AUTH_TOKEN'] = 'auth-token'

    def test_init_key_over_token(self):
        mail_client = TwilioEmailAPIClient()

        self.assertEqual(mail_client.username, 'api-key')
        self.assertEqual(mail_client.password, 'api-secret')
        self.assertEqual(mail_client.host, 'https://email.twilio.com')

    def test_init_token(self):
        del os.environ['TWILIO_API_KEY']
        del os.environ['TWILIO_API_SECRET']

        mail_client = TwilioEmailAPIClient()

        self.assertEqual(mail_client.username, 'account-sid')
        self.assertEqual(mail_client.password, 'auth-token')

    def test_init_args(self):
        mail_client = TwilioEmailAPIClient('username', 'password')

        self.assertEqual(mail_client.username, 'username')
        self.assertEqual(mail_client.password, 'password')
        self.assertEqual(mail_client.auth, 'Basic dXNlcm5hbWU6cGFzc3dvcmQ=')

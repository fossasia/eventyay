import os
import unittest

import sendgrid.helpers.inbound.config
from sendgrid.helpers.inbound.config import Config


class UnitTests(unittest.TestCase):

    def setUp(self):
        self.config = Config()

    def test_initialization(self):
        endpoint = '/inbound'
        port = 5000
        keys = [
            'from',
            'attachments',
            'headers',
            'text',
            'envelope',
            'to',
            'html',
            'sender_ip',
            'attachment-info',
            'subject',
            'dkim',
            'SPF',
            'charsets',
            'content-ids',
            'spam_report',
            'spam_score',
            'email',
        ]
        host = 'http://127.0.0.1:5000/inbound'

        self.assertTrue(self.config.debug_mode)
        self.assertEqual(self.config.endpoint, endpoint)
        self.assertEqual(self.config.host, host)
        self.assertEqual(self.config.port, port)
        for key in keys:
            self.assertIn(key, self.config.keys)

    def test_init_environment_should_set_env_from_dotenv(self):
        config_file = sendgrid.helpers.inbound.config.__file__
        env_file_path = '{0}/.env'.format(os.path.abspath(os.path.dirname(config_file)))
        with open(env_file_path, 'w') as f:
            f.write('RANDOM_VARIABLE=RANDOM_VALUE')
        Config()
        os.remove(env_file_path)
        self.assertEqual(os.environ['RANDOM_VARIABLE'], 'RANDOM_VALUE')

    def test_init_environment_should_not_set_env_if_format_is_invalid(self):
        config_file = sendgrid.helpers.inbound.config.__file__
        env_file_path = os.path.abspath(os.path.dirname(config_file)) + '/.env'
        with open(env_file_path, 'w') as f:
            f.write('RANDOM_VARIABLE=RANDOM_VALUE=ANOTHER_RANDOM_VALUE')
        Config()
        os.remove(env_file_path)
        self.assertIsNone(os.environ.get('RANDOM_VARIABLE'))

import os
import unittest

from sendgrid.helpers.inbound.config import Config
from sendgrid.helpers.inbound.app import app


class UnitTests(unittest.TestCase):

    def setUp(self):
        self.config = Config()
        app.testing = True
        self.tester = app.test_client(self)

    def test_up_and_running(self):
        response = self.tester.get('/')
        self.assertEqual(response.status_code, 200)

    def test_used_port_true(self):
        if self.config.debug_mode:
            port = int(os.environ.get("PORT", self.config.port))
            self.assertEqual(port, self.config.port)

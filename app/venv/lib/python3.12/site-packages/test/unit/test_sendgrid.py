import unittest
import sendgrid

class UnitTests(unittest.TestCase):
    def test_host_with_no_region(self):
        sg = sendgrid.SendGridAPIClient(api_key='MY_API_KEY')
        self.assertEqual("https://api.sendgrid.com",sg.client.host)

    def test_host_with_eu_region(self):
        sg = sendgrid.SendGridAPIClient(api_key='MY_API_KEY')
        sg.set_sendgrid_data_residency("eu")
        self.assertEqual("https://api.eu.sendgrid.com",sg.client.host)

    def test_host_with_global_region(self):
        sg = sendgrid.SendGridAPIClient(api_key='MY_API_KEY')
        sg.set_sendgrid_data_residency("global")
        self.assertEqual("https://api.sendgrid.com",sg.client.host)

    def test_with_region_is_none(self):
        sg = sendgrid.SendGridAPIClient(api_key='MY_API_KEY')
        with self.assertRaises(ValueError):
            sg.set_sendgrid_data_residency(None)

    def test_with_region_is_invalid(self):
        sg = sendgrid.SendGridAPIClient(api_key='MY_API_KEY')
        with self.assertRaises(ValueError):
            sg.set_sendgrid_data_residency("abc")
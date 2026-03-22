import json
import unittest

from sendgrid import EventWebhook


class UnitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.PUBLIC_KEY = 'MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAE83T4O/n84iotIvIW4mdBgQ/7dAfSmpqIM8kF9mN1flpVKS3GRqe62gw+2fNNRaINXvVpiglSI8eNEc6wEA3F+g=='
        cls.SIGNATURE = 'MEUCIGHQVtGj+Y3LkG9fLcxf3qfI10QysgDWmMOVmxG0u6ZUAiEAyBiXDWzM+uOe5W0JuG+luQAbPIqHh89M15TluLtEZtM='
        cls.TIMESTAMP = '1600112502'
        cls.PAYLOAD = json.dumps(
            [
                {
                    'email': 'hello@world.com',
                    'event': 'dropped',
                    'reason': 'Bounced Address',
                    'sg_event_id': 'ZHJvcC0xMDk5NDkxOS1MUnpYbF9OSFN0T0doUTRrb2ZTbV9BLTA',
                    'sg_message_id': 'LRzXl_NHStOGhQ4kofSm_A.filterdrecv-p3mdw1-756b745b58-kmzbl-18-5F5FC76C-9.0',
                    'smtp-id': '<LRzXl_NHStOGhQ4kofSm_A@ismtpd0039p1iad1.sendgrid.net>',
                    'timestamp': 1600112492,
                }
            ], sort_keys=True, separators=(',', ':')
        ) + '\r\n'  # Be sure to include the trailing carriage return and newline!

    def test_verify_valid_signature(self):
        ew = EventWebhook()
        key = ew.convert_public_key_to_ecdsa(self.PUBLIC_KEY)
        self.assertTrue(ew.verify_signature(self.PAYLOAD, self.SIGNATURE, self.TIMESTAMP, key))

    def test_verify_bad_key(self):
        ew = EventWebhook('MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEqTxd43gyp8IOEto2LdIfjRQrIbsd4SXZkLW6jDutdhXSJCWHw8REntlo7aNDthvj+y7GjUuFDb/R1NGe1OPzpA==')
        self.assertFalse(ew.verify_signature(self.PAYLOAD, self.SIGNATURE, self.TIMESTAMP))

    def test_verify_bad_payload(self):
        ew = EventWebhook(self.PUBLIC_KEY)
        self.assertFalse(ew.verify_signature('payload', self.SIGNATURE, self.TIMESTAMP))

    def test_verify_bad_signature(self):
        ew = EventWebhook(self.PUBLIC_KEY)
        self.assertFalse(ew.verify_signature(
            self.PAYLOAD,
            'MEUCIQCtIHJeH93Y+qpYeWrySphQgpNGNr/U+UyUlBkU6n7RAwIgJTz2C+8a8xonZGi6BpSzoQsbVRamr2nlxFDWYNH3j/0=',
            self.TIMESTAMP
        ))

    def test_verify_bad_timestamp(self):
        ew = EventWebhook(self.PUBLIC_KEY)
        self.assertFalse(ew.verify_signature(self.PAYLOAD, self.SIGNATURE, 'timestamp'))

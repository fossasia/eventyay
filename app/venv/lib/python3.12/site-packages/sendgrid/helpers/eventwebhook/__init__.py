from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import load_pem_public_key
import base64
from .eventwebhook_header import EventWebhookHeader

class EventWebhook:
    """
    This class allows you to use the Event Webhook feature. Read the docs for
    more details: https://sendgrid.com/docs/for-developers/tracking-events/event
    """

    def __init__(self, public_key=None):
        """
        Construct the Event Webhook verifier object
        :param public_key: verification key under Mail Settings
        :type public_key: string
        """
        self.public_key = self.convert_public_key_to_ecdsa(public_key) if public_key else public_key

    def convert_public_key_to_ecdsa(self, public_key):
        """
        Convert the public key string to an EllipticCurvePublicKey object.

        :param public_key: verification key under Mail Settings
        :type public_key string
        :return: An EllipticCurvePublicKey object using the ECDSA algorithm
        :rtype cryptography.hazmat.primitives.asymmetric.ec.EllipticCurvePublicKey
        """
        pem_key = "-----BEGIN PUBLIC KEY-----\n" + public_key + "\n-----END PUBLIC KEY-----"
        return load_pem_public_key(pem_key.encode("utf-8"))

    def verify_signature(self, payload, signature, timestamp, public_key=None):
        """
        Verify signed event webhook requests.

        :param payload: event payload in the request body
        :type payload: string
        :param signature: value obtained from the 'X-Twilio-Email-Event-Webhook-Signature' header
        :type signature: string
        :param timestamp: value obtained from the 'X-Twilio-Email-Event-Webhook-Timestamp' header
        :type timestamp: string
        :param public_key: elliptic curve public key
        :type public_key: cryptography.hazmat.primitives.asymmetric.ec.EllipticCurvePublicKey
        :return: true or false if signature is valid
        """
        timestamped_payload = (timestamp + payload).encode('utf-8')
        decoded_signature = base64.b64decode(signature)

        key = public_key or self.public_key
        try:
            key.verify(decoded_signature, timestamped_payload, ec.ECDSA(hashes.SHA256()))
            return True
        except InvalidSignature:
            return False

"""btcpay.client

BTCPay API Client.
"""

import re
import json
from urllib.parse import urlencode

import requests
from requests.exceptions import HTTPError

from . import crypto


class BTCPayClient:
    def __init__(self, host, pem, insecure=False, tokens=None):
        self.host = host
        self.verify = not(insecure)
        self.pem = pem
        self.tokens = tokens or dict()
        self.client_id = crypto.get_sin_from_pem(pem)
        self.user_agent = 'btcpay-python'
        self.s = requests.Session()
        self.s.verify = self.verify
        self.s.headers.update(
            {'Content-Type': 'application/json',
            'accept': 'application/json',
            'X-accept-version': '2.0.0'})

    def _create_signed_headers(self, uri, payload):
        return {
            "X-Identity": crypto.get_compressed_public_key_from_pem(self.pem),
            "X-Signature": crypto.sign(uri + payload, self.pem)
        }

    def _signed_get_request(self, path, params=None, token=None):
        token = token or list(self.tokens.values())[0]
        params = params or dict()
        params['token'] = token

        uri = self.host + path
        payload = '?' + urlencode(params)
        headers = self._create_signed_headers(uri, payload)
        r = self.s.get(uri, params=params, headers=headers)
        r.raise_for_status()
        return r.json()['data']

    def _signed_post_request(self, path, payload, token=None):
        token = token or list(self.tokens.values())[0]
        uri = self.host + path
        payload['token'] = token
        payload = json.dumps(payload)
        headers = self._create_signed_headers(uri, payload)
        r = self.s.post(uri, headers=headers, data=payload)
        if not r.ok:
            if 400 <= r.status_code < 500:
                http_error_msg = u'%s Client Error: \
                        %s for url: %s | body: %s' % (
                            r.status_code,
                            r.reason,
                            r.url,
                            r.text
                        )
            elif 500 <= r.status_code < 600:
                http_error_msg = u'%s Server Error: \
                        %s for url: %s | body: %s' % (
                            r.status_code,
                            r.reason,
                            r.url,
                            r.text
                        )
            if http_error_msg:
                raise HTTPError(http_error_msg, response=r)
        return r.json()['data']

    def _unsigned_request(self, path, payload=None):
        uri = self.host + path
        if payload:
            payload = json.dumps(payload)
            r = self.s.post(uri, data=payload)
        else:
            r = self.s.get(uri)
        r.raise_for_status()
        return r.json()['data']

    def get_rates(self, crypto='BTC', store_id=None):
        params = dict(
            cryptoCode=crypto
        )
        if store_id:
            params['storeID'] = store_id
        return self._signed_get_request('/rates/', params=params)

    def get_rate(self, currency, crypto='BTC', store_id=None):
        rates = self.get_rates(crypto=crypto, store_id=store_id)
        rate = [rate for rate in rates if rate['code'] == currency.upper()][0]
        return rate['rate']

    def create_invoice(self, payload, token=None):
        try:
            float(payload['price'])
        except ValueError as e:
            raise ValueError('Price must be a float') from e
        return self._signed_post_request('/invoices/', payload, token=token)

    def get_invoice(self, invoice_id, token=None):
        return self._signed_get_request('/invoices/' + invoice_id, token=token)

    def get_invoices(self, status=None, order_id=None, item_code=None, date_start=None, date_end=None, limit=None, offset=None, token=None):
        params = dict()
        if status is not None:
            params['status'] = status
        if order_id is not None:
            params['orderId'] = order_id
        if item_code is not None:
            params['itemCode'] = item_code
        if date_start is not None:
            params['dateStart'] = date_start
        if date_end is not None:
            params['dateEnd'] = date_end
        if limit is not None:
            params['limit'] = limit
        if offset is not None:
            params['offset'] = offset
        return self._signed_get_request('/invoices', params=params, token=token)

    def pair_client(self, code):
        if re.match(r'^\w{7,7}$', code) is None:
          raise ValueError("pairing code is not legal")
        payload = {'id': self.client_id, 'pairingCode': code}
        data = self._unsigned_request('/tokens', payload)
        data = data[0]
        return {
            data['facade']: data['token']
        }

    @classmethod
    def create_client(cls, code, host):
        pem = crypto.generate_privkey()
        client = BTCPayClient(host=host, pem=pem)
        token = client.pair_client(code)
        return BTCPayClient(host=host, pem=pem, tokens=token)

    @classmethod
    def create_tor_client(cls, code, host, proxy='socks5://127.0.0.1:9050'):
        """ Useful for .onion services, the `proxy` input assumes the default
        proxy header
        """
        pem = crypto.generate_privkey()
        client = BTCPayClient(host=host, pem=pem)
        client.s.proxies = {
            'http': proxy,
            'https': proxy}
        token = client.pair_client(code)
        final_client = BTCPayClient(host=host, pem=pem, tokens=token)
        final_client.s.proxies = {
            'http': proxy,
            'https': proxy}
        return final_client


    def __repr__(self):
        return '{}({})'.format(
            type(self).__name__,
            self.host
        )

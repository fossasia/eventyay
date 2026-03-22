# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from xml.etree import ElementTree
import cgi
from decimal import Decimal

try:
    # Python 3
    from urllib.request import urlopen
    str_cls = str
except (ImportError):
    # Python 2
    from urllib2 import urlopen
    str_cls = unicode

try:
    from money import xrates
except (ImportError):
    xrates = None

from .errors import WebServiceError
builtin_format = format


def fetch():
    """
    Fetches the latest exchange rate info from the European Central Bank. These
    rates need to be used for displaying invoices since some countries require
    local currency be quoted. Also useful to store the GBP rate of the VAT
    collected at time of purchase to prevent fluctuations in exchange rates from
    significantly altering the amount of tax due the HMRC (if you are using them
    for VAT MOSS).

    :return:
        A dict with string keys that are currency codes and values that are
        Decimals of the exchange rate with the base (1.0000) being the Euro
        (EUR). The following currencies are included, based on this library
        being build for EU and Norway VAT, plus USD for the author:
         - BGN
         - CZK
         - DKK
         - EUR
         - GBP
         - HUF
         - HRK
         - NOK
         - PLN
         - RON
         - SEK
         - USD
    """

    response = urlopen('https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml')
    _, params = cgi.parse_header(response.headers['Content-Type'])
    if 'charset' in params:
        encoding = params['charset']
    else:
        encoding = 'utf-8'

    return_xml = response.read().decode(encoding)

    # Example return data
    #
    # <gesmes:Envelope xmlns:gesmes="http://www.gesmes.org/xml/2002-08-01" xmlns="http://www.ecb.int/vocabulary/2002-08-01/eurofxref">
    #     <gesmes:subject>Reference rates</gesmes:subject>
    #     <gesmes:Sender>
    #         <gesmes:name>European Central Bank</gesmes:name>
    #     </gesmes:Sender>
    #     <Cube>
    #         <Cube time="2015-01-09">
    #             <Cube currency="USD" rate="1.1813"/>
    #             <Cube currency="JPY" rate="140.81"/>
    #             <Cube currency="BGN" rate="1.9558"/>
    #             <Cube currency="CZK" rate="28.062"/>
    #             <Cube currency="DKK" rate="7.4393"/>
    #             <Cube currency="GBP" rate="0.77990"/>
    #             <Cube currency="HUF" rate="317.39"/>
    #             <Cube currency="PLN" rate="4.2699"/>
    #             <Cube currency="RON" rate="4.4892"/>
    #             <Cube currency="SEK" rate="9.4883"/>
    #             <Cube currency="CHF" rate="1.2010"/>
    #             <Cube currency="NOK" rate="9.0605"/>
    #             <Cube currency="HRK" rate="7.6780"/>
    #             <Cube currency="RUB" rate="72.8910"/>
    #             <Cube currency="TRY" rate="2.7154"/>
    #             <Cube currency="AUD" rate="1.4506"/>
    #             <Cube currency="BRL" rate="3.1389"/>
    #             <Cube currency="CAD" rate="1.3963"/>
    #             <Cube currency="CNY" rate="7.3321"/>
    #             <Cube currency="HKD" rate="9.1593"/>
    #             <Cube currency="IDR" rate="14925.34"/>
    #             <Cube currency="ILS" rate="4.6614"/>
    #             <Cube currency="INR" rate="73.6233"/>
    #             <Cube currency="KRW" rate="1290.29"/>
    #             <Cube currency="MXN" rate="17.3190"/>
    #             <Cube currency="MYR" rate="4.2054"/>
    #             <Cube currency="NZD" rate="1.5115"/>
    #             <Cube currency="PHP" rate="53.090"/>
    #             <Cube currency="SGD" rate="1.5789"/>
    #             <Cube currency="THB" rate="38.846"/>
    #             <Cube currency="ZAR" rate="13.6655"/>
    #         </Cube>
    #     </Cube>
    # </gesmes:Envelope>

    # If we don't explicitly recode to UTF-8, ElementTree stupidly uses
    # ascii on Python 2.7
    envelope = ElementTree.fromstring(return_xml.encode('utf-8'))

    namespaces = {
        'gesmes': 'http://www.gesmes.org/xml/2002-08-01',
        'eurofxref': 'http://www.ecb.int/vocabulary/2002-08-01/eurofxref'
    }

    date_elements = envelope.findall('./eurofxref:Cube/eurofxref:Cube[@time]', namespaces)
    if not date_elements:
        # Fail loudly if the XML seems to have changed
        raise WebServiceError('Unable to find <Cube time=""> tag in ECB XML')

    date = date_elements[0].get('time')
    if not isinstance(date, str_cls):
        date = date.decode('utf-8')

    currency_elements = envelope.findall('./eurofxref:Cube/eurofxref:Cube/eurofxref:Cube[@currency][@rate]', namespaces)
    if not currency_elements:
        # Fail loudly if the XML seems to have changed
        raise WebServiceError('Unable to find <Cube currency="" rate=""> tags in ECB XML')

    rates = {
        'EUR': Decimal('1.0000')
    }

    applicable_currenties = {
        'BGN': True,
        'CZK': True,
        'DKK': True,
        'EUR': True,
        'GBP': True,
        'HRK': True,
        'HUF': True,
        'NOK': True,
        'PLN': True,
        'RON': True,
        'SEK': True,
        'USD': True
    }

    for currency_element in currency_elements:
        code = currency_element.attrib.get('currency')

        if code not in applicable_currenties:
            continue

        rate = currency_element.attrib.get('rate')
        rates[code] = Decimal(rate)

    return (date, rates)


def setup_xrates(base, rates):
    """
    If using the Python money package, this will set up the xrates exchange
    rate data.

    :param base:
        The string currency code to use as the base

    :param rates:
        A dict with keys that are string currency codes and values that are
        a Decimal of the exchange rate for that currency.
    """

    xrates.install('money.exchange.SimpleBackend')
    xrates.base = base
    for code, value in rates.items():
        xrates.setrate(code, value)


def format(amount, currency=None):
    """
    Formats a decimal or Money object into an unambiguous string representation
    for the purpose of invoices in English.

    :param amount:
        A Decimal or Money object

    :param currency:
        If the amount is a Decimal, the currency of the amount

    :return:
        A string representation of the amount in the currency
    """

    if currency is None and hasattr(amount, 'currency'):
        currency = amount.currency

    # Allow Money objects
    if not isinstance(amount, Decimal) and hasattr(amount, 'amount'):
        amount = amount.amount

    if not isinstance(currency, str_cls):
        raise ValueError('The currency specified is not a string')

    if currency not in FORMATTING_RULES:
        valid_currencies = sorted(FORMATTING_RULES.keys())
        formatted_currencies = ', '.join(valid_currencies)
        raise ValueError('The currency specified, "%s", is not a supported currency: %s' % (currency, formatted_currencies))

    if not isinstance(amount, Decimal):
        raise ValueError('The amount specified is not a Decimal')

    rules = FORMATTING_RULES[currency]

    format_string = ',.%sf' % rules['decimal_places']

    result = builtin_format(amount, format_string)

    result = result.replace(',', '_')
    result = result.replace('.', '|')

    result = result.replace('_', rules['thousands_separator'])
    result = result.replace('|', rules['decimal_mark'])

    if rules['symbol_first']:
        result = rules['symbol'] + result
    else:
        result = result + rules['symbol']

    return result


FORMATTING_RULES = {
    'BGN': {
        'symbol': ' Lev',
        'symbol_first': False,
        'decimal_mark': '.',
        'thousands_separator': ',',
        'decimal_places': 2
    },
    'CZK': {
        'symbol': ' Kč',
        'symbol_first': False,
        'decimal_mark': ',',
        'thousands_separator': '.',
        'decimal_places': 2
    },
    'DKK': {
        'symbol': ' Dkr',
        'symbol_first': False,
        'decimal_mark': ',',
        'thousands_separator': '.',
        'decimal_places': 2
    },
    'EUR': {
        'symbol': '€',
        'symbol_first': True,
        'decimal_mark': ',',
        'thousands_separator': '.',
        'decimal_places': 2
    },
    'GBP': {
        'symbol': '£',
        'symbol_first': True,
        'decimal_mark': '.',
        'thousands_separator': ',',
        'decimal_places': 2
    },
    'HRK': {
        'symbol': ' Kn',
        'symbol_first': False,
        'decimal_mark': ',',
        'thousands_separator': '.',
        'decimal_places': 2
    },
    'HUF': {
        'symbol': ' Ft',
        'symbol_first': False,
        'decimal_mark': ',',
        'thousands_separator': '.',
        'decimal_places': 2
    },
    'NOK': {
        'symbol': ' Nkr',
        'symbol_first': False,
        'decimal_mark': ',',
        'thousands_separator': '.',
        'decimal_places': 2
    },
    'PLN': {
        'symbol': ' Zł',
        'symbol_first': False,
        'decimal_mark': ',',
        'thousands_separator': ' ',
        'decimal_places': 2
    },
    'RON': {
        'symbol': ' Lei',
        'symbol_first': False,
        'decimal_mark': ',',
        'thousands_separator': '.',
        'decimal_places': 2
    },
    'SEK': {
        'symbol': ' Skr',
        'symbol_first': False,
        'decimal_mark': ',',
        'thousands_separator': ' ',
        'decimal_places': 2
    },
    'USD': {
        'symbol': '$',
        'symbol_first': True,
        'decimal_mark': '.',
        'thousands_separator': ',',
        'decimal_places': 2
    }
}

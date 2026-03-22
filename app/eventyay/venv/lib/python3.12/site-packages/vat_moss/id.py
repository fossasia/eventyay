# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import re
import json
from xml.etree import ElementTree
import cgi

try:
    # Python 3
    from urllib.request import Request, urlopen
    from urllib.error import HTTPError
    str_cls = str
except (ImportError):
    # Python 2
    from urllib2 import Request, urlopen, HTTPError
    str_cls = unicode

from .errors import InvalidError, WebServiceError, WebServiceUnavailableError


def normalize(vat_id):
    """
    Accepts a VAT ID and normaizes it, getting rid of spaces, periods, dashes
    etc and converting it to upper case.

    :param vat_id:
        The VAT ID to check. Allows "GR" prefix for Greece, even though it
        should be "EL".

    :raises:
        ValueError - If the is not a string or is not in the format of two characters plus an identifier

    :return:
        None if the VAT ID is blank or not for an EU country or Norway
        Otherwise a normalized string containing the VAT ID
    """

    if not vat_id:
        return None

    if not isinstance(vat_id, str_cls):
        raise ValueError('VAT ID is not a string')

    if len(vat_id) < 3:
        raise ValueError('VAT ID must be at least three character long')

    # Normalize the ID for simpler regexes
    vat_id = re.sub('\\s+', '', vat_id)
    vat_id = vat_id.replace('-', '')
    vat_id = vat_id.replace('.', '')
    vat_id = vat_id.upper()

    country_prefix = vat_id[0:2]

    # Fix people using GR prefix for Greece
    if country_prefix == 'GR':
        vat_id = 'EL' + vat_id[2:]
        country_prefix = 'EL'

    if country_prefix not in ID_PATTERNS:
        return None

    return vat_id


def validate(vat_id):
    """
    Runs some basic checks to ensure a VAT ID looks properly formatted. If so,
    checks it against the VIES system for EU VAT IDs or data.brreg.no for
    Norwegian VAT ID.

    :param vat_id:
        The VAT ID to check. Allows "GR" prefix for Greece, even though it
        should be "EL".

    :raises:
        ValueError - If the is not a string or is not in the format of two characters plus an identifier
        InvalidError - If the VAT ID is not valid
        WebServiceUnavailableError - If the VIES VAT ID service is unable to process the request - this is fairly common
        WebServiceError - If there was an error parsing the response from the server - usually this means something changed in the webservice
        urllib.error.URLError/urllib2.URLError - If there is an issue communicating with VIES or data.brreg.no

    :return:
        None if the VAT ID is blank or not for an EU country or Norway
        A tuple of (two-character country code, normalized VAT id, company name) if valid
    """

    vat_id = normalize(vat_id)

    if not vat_id:
        return vat_id

    country_prefix = vat_id[0:2]

    number = vat_id[2:]

    if not re.match(ID_PATTERNS[country_prefix]['regex'], number):
        raise InvalidError('VAT ID does not appear to be properly formatted for %s' % country_prefix)

    if country_prefix == 'NO':
        organization_number = number.replace('MVA', '')
        validation_url = 'http://data.brreg.no/enhetsregisteret/enhet/%s.json' % organization_number

        try:
            response = urlopen(validation_url)
            _, params = cgi.parse_header(response.headers['Content-Type'])
            if 'charset' in params:
                encoding = params['charset']
            else:
                encoding = 'utf-8'

            return_json = response.read().decode(encoding)

            # Example response:
            #
            # {
            #     "organisasjonsnummer": 974760673,
            #     "navn": "REGISTERENHETEN I BRØNNØYSUND",
            #     "registreringsdatoEnhetsregisteret": "1995-08-09",
            #     "organisasjonsform": "ORGL",
            #     "hjemmeside": "www.brreg.no",
            #     "registrertIFrivillighetsregisteret": "N",
            #     "registrertIMvaregisteret": "N",
            #     "registrertIForetaksregisteret": "N",
            #     "registrertIStiftelsesregisteret": "N",
            #     "antallAnsatte": 562,
            #     "institusjonellSektorkode": {
            #         "kode": "6100",
            #         "beskrivelse": "Statsforvaltningen"
            #     },
            #     "naeringskode1": {
            #         "kode": "84.110",
            #         "beskrivelse": "Generell offentlig administrasjon"
            #     },
            #     "postadresse": {
            #         "adresse": "Postboks 900",
            #         "postnummer": "8910",
            #         "poststed": "BRØNNØYSUND",
            #         "kommunenummer": "1813",
            #         "kommune": "BRØNNØY",
            #         "landkode": "NO",
            #         "land": "Norge"
            #     },
            #     "forretningsadresse": {
            #         "adresse": "Havnegata 48",
            #         "postnummer": "8900",
            #         "poststed": "BRØNNØYSUND",
            #         "kommunenummer": "1813",
            #         "kommune": "BRØNNØY",
            #         "landkode": "NO",
            #         "land": "Norge"
            #     },
            #     "konkurs": "N",
            #     "underAvvikling": "N",
            #     "underTvangsavviklingEllerTvangsopplosning": "N",
            #     "overordnetEnhet": 912660680,
            #     "links": [
            #         {
            #             "rel": "self",
            #             "href": "http://data.brreg.no/enhetsregisteret/enhet/974760673"
            #         },
            #         {
            #             "rel": "overordnetEnhet",
            #             "href": "http://data.brreg.no/enhetsregisteret/enhet/912660680"
            #         }
            #     ]
            # }

            info = json.loads(return_json)

            # This should never happen, but keeping it incase the API is changed
            if 'organisasjonsnummer' not in info or info['organisasjonsnummer'] != int(organization_number):
                raise WebServiceError('No or different value for the "organisasjonsnummer" key in response from data.brreg.no')

            company_name = info['organisasjonsnummer']

        except (HTTPError) as e:
            # If a number is invalid, we get a 404
            if e.code == 404:
                raise InvalidError('VAT ID is invalid')

            # If we get anything but a 404 we want the exception to be recorded
            raise

    # EU countries
    else:
        post_data = '''
            <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:urn="urn:ec.europa.eu:taxud:vies:services:checkVat:types">
               <soapenv:Header/>
               <soapenv:Body>
                  <urn:checkVat>
                     <urn:countryCode>%s</urn:countryCode>
                     <urn:vatNumber>%s</urn:vatNumber>
                  </urn:checkVat>
               </soapenv:Body>
            </soapenv:Envelope>
        ''' % (country_prefix, number)

        request = Request('https://ec.europa.eu/taxation_customs/vies/services/checkVatService')
        request.add_header('Content-Type', 'application/x-www-form-urlencoded; charset=utf-8')

        try:
            response = urlopen(request, post_data.encode('utf-8'))
        except (HTTPError) as e:
            # If one of the country VAT ID services is down, we get a 500
            if e.code == 500:
                raise WebServiceUnavailableError('VAT ID validation is not currently available')

            # If we get anything but a 500 we want the exception to be recorded
            raise

        _, params = cgi.parse_header(response.headers['Content-Type'])
        if 'charset' in params:
            encoding = params['charset']
        else:
            encoding = 'utf-8'

        return_xml = response.read().decode(encoding)

        # Example response:
        #
        # <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
        #    <soap:Body>
        #       <checkVatResponse xmlns="urn:ec.europa.eu:taxud:vies:services:checkVat:types">
        #          <countryCode>GB</countryCode>
        #          <vatNumber>GD001</vatNumber>
        #          <requestDate>2014-12-17+01:00</requestDate>
        #          <valid>true</valid>
        #          <name>MINISTRY OF AGRICULTURE FISHERIES &amp; FOOD</name>
        #          <address>ROOM C206
        # GOVERNMENT BUILDINGS
        # EPSOM ROAD
        # GUILDFORD
        # SURREY
        # GU1 2LD</address>
        #       </checkVatResponse>
        #    </soap:Body>
        # </soap:Envelope>

        try:
            # If we don't explicitly recode to UTF-8, ElementTree stupidly uses
            # ascii on Python 2.7
            envelope = ElementTree.fromstring(return_xml.encode('utf-8'))
        except (ElementTree.ParseError):
            raise WebServiceError('Unable to parse response from VIES')

        namespaces = {
            'soap': 'http://schemas.xmlsoap.org/soap/envelope/',
            'vat':  'urn:ec.europa.eu:taxud:vies:services:checkVat:types'
        }
        valid_elements = envelope.findall('./soap:Body/vat:checkVatResponse/vat:valid', namespaces)
        if not valid_elements:
            # Fail loudly if the XML seems to have changed
            raise WebServiceError('Unable to find <valid> tag in response from VIES')

        name_elements = envelope.findall('./soap:Body/vat:checkVatResponse/vat:name', namespaces)
        if not name_elements:
            # Fail loudly if the XML seems to have changed
            raise WebServiceError('Unable to find <name> tag in response from VIES')

        if valid_elements[0].text.lower() != 'true':
            raise InvalidError('VAT ID is invalid')

        company_name = name_elements[0].text

    return (ID_PATTERNS[country_prefix]['country_code'], vat_id, company_name)


# Patterns generated by consulting the following URLs:
#
#  - http://en.wikipedia.org/wiki/VAT_identification_number
#  - http://ec.europa.eu/taxation_customs/vies/faq.html
#  - http://www.skatteetaten.no/en/International-pages/Felles-innhold-benyttes-i-flere-malgrupper/Brochure/Guide-to-value-added-tax-in-Norway/?chapter=7159
ID_PATTERNS = {
    'AT': {  # Austria
        'regex': '^U\\d{8}$',
        'country_code': 'AT'
    },
    'BE': {  # Belgium
        'regex': '^(1|0?)\\d{9}$',
        'country_code': 'BE'
    },
    'BG': {  # Bulgaria
        'regex': '^\\d{9,10}$',
        'country_code': 'BG'
    },
    'CY': {  # Cyprus
        'regex': '^\\d{8}[A-Z]$',
        'country_code': 'CY'
    },
    'CZ': {  # Czech Republic
        'regex': '^\\d{8,10}$',
        'country_code': 'CZ'
    },
    'DE': {  # Germany
        'regex': '^\\d{9}$',
        'country_code': 'DE'
    },
    'DK': {  # Denmark
        'regex': '^\\d{8}$',
        'country_code': 'DK'
    },
    'EE': {  # Estonia
        'regex': '^\\d{9}$',
        'country_code': 'EE'
    },
    'EL': {  # Greece
        'regex': '^\\d{9}$',
        'country_code': 'GR'
    },
    'ES': {  # Spain
        'regex': '^[A-Z0-9]\\d{7}[A-Z0-9]$',
        'country_code': 'ES'
    },
    'FI': {  # Finland
        'regex': '^\\d{8}$',
        'country_code': 'FI'
    },
    'FR': {  # France
        'regex': '^[A-Z0-9]{2}\\d{9}$',
        'country_code': 'FR'
    },
    'GB': {  # United Kingdom
        'regex': '^(GD\\d{3}|HA\\d{3}|\\d{9}|\\d{12})$',
        'country_code': 'GB'
    },
    'HR': {  # Croatia
        'regex': '^\\d{11}$',
        'country_code': 'HR'
    },
    'HU': {  # Hungary
        'regex': '^\\d{8}$',
        'country_code': 'HU'
    },
    'IE': {  # Ireland
        'regex': '^(\\d{7}[A-Z]{1,2}|\\d[A-Z+*]\\d{5}[A-Z])$',
        'country_code': 'IE'
    },
    'IT': {  # Italy
        'regex': '^\\d{11}$',
        'country_code': 'IT'
    },
    'LT': {  # Lithuania
        'regex': '^(\\d{9}|\\d{12})$',
        'country_code': 'LT'
    },
    'LU': {  # Luxembourg
        'regex': '^\\d{8}$',
        'country_code': 'LU'
    },
    'LV': {  # Latvia
        'regex': '^\\d{11}$',
        'country_code': 'LV'
    },
    'MT': {  # Malta
        'regex': '^\\d{8}$',
        'country_code': 'MT'
    },
    'NL': {  # Netherlands
        'regex': '^\\d{9}B\\d{2}$',
        'country_code': 'NL'
    },
    'NO': {  # Norway
        'regex': '^\\d{9}MVA$',
        'country_code': 'NO'
    },
    'PL': {  # Poland
        'regex': '^\\d{10}$',
        'country_code': 'PL'
    },
    'PT': {  # Portugal
        'regex': '^\\d{9}$',
        'country_code': 'PT'
    },
    'RO': {  # Romania
        'regex': '^\\d{2,10}$',
        'country_code': 'RO'
    },
    'SE': {  # Sweden
        'regex': '^\\d{12}$',
        'country_code': 'SE'
    },
    'SI': {  # Slovenia
        'regex': '^\\d{8}$',
        'country_code': 'SI'
    },
    'SK': {  # Slovakia
        'regex': '^\\d{10}$',
        'country_code': 'SK'
    },
}

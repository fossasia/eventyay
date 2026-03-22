import requests
import xml.dom.minidom

from requests import Timeout

from .result import VatNumberCheckResult
from .xml_utils import get_first_child_element, get_text, NodeNotFoundError
from .exceptions import ServerError


class Registry(object):
    """Abstract base registry.

    Defines an explicit interface for accessing arbitary registries.
    """

    def check_vat_number(self, vat_number, country_code):
        """Check if a VAT number is valid according to the registry.

        :param vat_number: VAT number without country code prefix.
        :param country_code: ISO 3166-1-alpha-2 country code.
        :returns: a :class:`VatNumberCheckResult` instance.
        """

        raise NotImplementedError()


class ViesRegistry(Registry):
    """VIES registry.

    Uses the European Commision's VIES registry for validating VAT numbers.
    """

    CHECK_VAT_SERVICE_URL = 'http://ec.europa.eu/taxation_customs/vies/' \
        'services/checkVatService'
    """URL for the VAT checking service.
    """

    DEFAULT_TIMEOUT = 8
    """Timeout for the requests."""

    def check_vat_number(self, vat_number, country_code):
        # Non-ISO code used for Greece.
        if country_code == 'GR':
            country_code = 'EL'

        # Request information about the VAT number.
        result = VatNumberCheckResult()

        request_data = (
                u'<?xml version="1.0" encoding="UTF-8"?><SOAP-ENV:Envelope'
                u' xmlns:ns0="urn:ec.europa.eu:taxud:vies:services:checkVa'
                u't:types" xmlns:ns1="http://schemas.xmlsoap.org/soap/enve'
                u'lope/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-insta'
                u'nce" xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/env'
                u'elope/"><SOAP-ENV:Header/><ns1:Body><ns0:checkVat><ns0:c'
                u'ountryCode>%s</ns0:countryCode><ns0:vatNumber>%s</ns0:va'
                u'tNumber></ns0:checkVat></ns1:Body></SOAP-ENV:Envelope>' %
                (country_code, vat_number)
        )

        result.log_lines += [
            u'> POST %s with payload of content type text/xml, charset UTF-8:',
            request_data,
        ]

        try:
            response = requests.post(
                self.CHECK_VAT_SERVICE_URL,
                data=request_data.encode('utf-8'),
                headers={
                    'Content-Type': 'text/xml; charset=utf-8',
                },
                timeout=self.DEFAULT_TIMEOUT
            )
        except Timeout as e:
            result.log_lines.append(u'< Request to EU VIEW registry timed out:'
                                    u' {}'.format(e))
            return result
        except Exception as exception:
            # Do not completely fail problematic requests.
            result.log_lines.append(u'< Request failed with exception: %r' %
                                    (exception))
            return result

        # Log response information.
        result.log_lines += [
            u'< Response with status %d of content type %s:' %
            (response.status_code, response.headers['Content-Type']),
            response.text,
            ]

        # Do not completely fail problematic requests.
        if response.status_code != 200 or \
                not response.headers['Content-Type'].startswith('text/xml'):
            result.log_lines.append(u'< Response is nondeterministic due to '
                                    u'invalid response status code or MIME '
                                    u'type')
            return result

        # Parse the DOM and validate as much as we can.
        #
        # We basically expect the result structure to be as follows,
        # where the address and name nodes might be omitted.
        #
        # <env:Envelope
	    #     xmlns:env="http://schemas.xmlsoap.org/soap/envelope/">
        #         <env:Header/>
        #         <env:Body>
        #         <ns2:checkVatResponse
        #              xmlns:ns2="urn:ec.europa.eu:taxud:vies:services:checkVat:types">
        #              <ns2:countryCode>DE</ns2:countryCode>
        #              <ns2:vatNumber>812383453</ns2:vatNumber>
        #              <ns2:requestDate>2022-08-12+02:00</ns2:requestDate>
        #              <ns2:valid>true</ns2:valid>
        #              <ns2:name>---</ns2:name>
        #              <ns2:address>---</ns2:address>
        #         </ns2:checkVatResponse>
        #     </env:Body>
        # </env:Envelope>
        result_dom = xml.dom.minidom.parseString(response.text.encode('utf-8'))

        envelope_node = result_dom.documentElement
        if envelope_node.tagName != 'env:Envelope':
            raise ValueError(
                'expected response XML root element to be a SOAP envelope'
            )

        body_node = get_first_child_element(envelope_node, 'env:Body')

        # Check for server errors
        try:
            error_node = get_first_child_element(body_node, 'env:Fault')
            fault_strings = error_node.getElementsByTagName('faultstring')
            fault_code = fault_strings[0].firstChild.nodeValue
            raise ServerError(fault_code)
        except NodeNotFoundError:
            pass

        try:
            check_vat_response_node = get_first_child_element(
                body_node,
                'ns2:checkVatResponse'
            )
            valid_node = get_first_child_element(
                check_vat_response_node,
                'ns2:valid'
            )
        except Exception as e:
            result.log_lines.append(u'< Response is nondeterministic due to '
                                    u'invalid response body: %r' % (e))
            return result

        # Parse the validity of the business.
        valid_text = get_text(valid_node)

        if valid_text in frozenset(('true', 'false')):
            result.is_valid = valid_text == 'true'
        else:
            result.log_lines.append(u'< Response is nondeterministic due to '
                                    u'invalid validity field: %r' %
                                    (valid_text))

        # Parse the business name and address if possible.
        try:
            name_node = get_first_child_element(
                check_vat_response_node,
                'ns2:name'
            )
            result.business_name = get_text(name_node).strip() or None
        except Exception:
            pass

        try:
            address_node = get_first_child_element(
                check_vat_response_node,
                'ns2:address'
            )
            result.business_address = get_text(address_node).strip() or None
        except Exception:
            pass
        
        # Parse the country code if possible.
        try:
            country_code_node = get_first_child_element(
                check_vat_response_node,
                'ns2:countryCode'
            )
            result.business_country_code = get_text(country_code_node).strip() or None
        except Exception:
            pass

        return result


__all__ = ('Registry', 'ViesRegistry', )

"""Auto-generated file, do not edit by hand. PY metadata"""
from ..phonemetadata import NumberFormat, PhoneNumberDesc, PhoneMetadata

PHONE_METADATA_PY = PhoneMetadata(id='PY', country_code=None, international_prefix=None,
    general_desc=PhoneNumberDesc(national_number_pattern='[12459]\\d\\d(?:\\d{3,4})?', possible_length=(3, 6, 7)),
    toll_free=PhoneNumberDesc(national_number_pattern='128|911', example_number='128', possible_length=(3,)),
    emergency=PhoneNumberDesc(national_number_pattern='128|911', example_number='128', possible_length=(3,)),
    short_code=PhoneNumberDesc(national_number_pattern='[1245][01]\\d{5}|(?:1[1-9]|[245]0\\d{3})\\d|911', example_number='110', possible_length=(3, 6, 7)),
    carrier_specific=PhoneNumberDesc(national_number_pattern='[1245][01]\\d{5}|[245]0\\d{4}', example_number='200000', possible_length=(6, 7)),
    sms_services=PhoneNumberDesc(national_number_pattern='[1245][01]\\d{5}|[245]0\\d{4}', example_number='200000', possible_length=(6, 7)),
    short_data=True)

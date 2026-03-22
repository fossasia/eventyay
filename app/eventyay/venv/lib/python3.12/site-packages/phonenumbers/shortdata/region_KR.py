"""Auto-generated file, do not edit by hand. KR metadata"""
from ..phonemetadata import NumberFormat, PhoneNumberDesc, PhoneMetadata

PHONE_METADATA_KR = PhoneMetadata(id='KR', country_code=None, international_prefix=None,
    general_desc=PhoneNumberDesc(national_number_pattern='1\\d\\d(?:\\d(?:\\d(?:\\d{3})?)?)?', possible_length=(3, 4, 5, 8)),
    toll_free=PhoneNumberDesc(national_number_pattern='1(?:1[27-9]|28|330|82)', example_number='112', possible_length=(3, 4)),
    emergency=PhoneNumberDesc(national_number_pattern='11[29]', example_number='112', possible_length=(3,)),
    short_code=PhoneNumberDesc(national_number_pattern='1(?:[01679]114|3(?:0[01]|2|3[0-35-9]|45?|5[057]|6[569]|7[79]|8[2589]|9[0189])|55[15]\\d{4}|8(?:(?:11|44|66)\\d{4}|[28]))|1(?:0[015]|1\\d|2[01357-9]|41|8114)', example_number='100', possible_length=(3, 4, 5, 8)),
    carrier_specific=PhoneNumberDesc(national_number_pattern='1(?:0[01]|1[4-6]|41|8114)|1(?:[0679]1\\d|111)\\d', example_number='100', possible_length=(3, 5)),
    sms_services=PhoneNumberDesc(national_number_pattern='1(?:55|8[146])\\d{5}', example_number='15500000', possible_length=(8,)),
    short_data=True)

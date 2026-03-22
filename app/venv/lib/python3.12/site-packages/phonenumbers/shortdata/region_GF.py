"""Auto-generated file, do not edit by hand. GF metadata"""
from ..phonemetadata import NumberFormat, PhoneNumberDesc, PhoneMetadata

PHONE_METADATA_GF = PhoneMetadata(id='GF', country_code=None, international_prefix=None,
    general_desc=PhoneNumberDesc(national_number_pattern='[13]\\d(?:\\d\\d(?:\\d{2})?)?', possible_length=(2, 4, 6)),
    toll_free=PhoneNumberDesc(national_number_pattern='1[578]|3(?:0\\d|1[0-689])\\d', example_number='15', possible_length=(2, 4)),
    premium_rate=PhoneNumberDesc(national_number_pattern='3[2469]\\d\\d', example_number='3200', possible_length=(4,)),
    emergency=PhoneNumberDesc(national_number_pattern='1[578]', example_number='15', possible_length=(2,)),
    short_code=PhoneNumberDesc(national_number_pattern='1[578]|300[0-79]|(?:118[02-9]\\d|3(?:0[1-9]|1[0-689]|[2469]\\d))\\d', example_number='15', possible_length=(2, 4, 6)),
    short_data=True)

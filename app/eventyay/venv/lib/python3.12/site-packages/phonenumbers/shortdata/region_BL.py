"""Auto-generated file, do not edit by hand. BL metadata"""
from ..phonemetadata import NumberFormat, PhoneNumberDesc, PhoneMetadata

PHONE_METADATA_BL = PhoneMetadata(id='BL', country_code=None, international_prefix=None,
    general_desc=PhoneNumberDesc(national_number_pattern='[13]\\d(?:\\d\\d(?:\\d{2})?)?', possible_length=(2, 4, 6)),
    toll_free=PhoneNumberDesc(national_number_pattern='18|3(?:00|1[0-689])\\d', example_number='18', possible_length=(2, 4)),
    premium_rate=PhoneNumberDesc(national_number_pattern='3[2469]\\d\\d', example_number='3200', possible_length=(4,)),
    emergency=PhoneNumberDesc(national_number_pattern='18', example_number='18', possible_length=(2,)),
    short_code=PhoneNumberDesc(national_number_pattern='18|3(?:00[0-79]|1[0-689]\\d)|(?:118[02-9]|3[2469])\\d\\d', example_number='18', possible_length=(2, 4, 6)),
    short_data=True)

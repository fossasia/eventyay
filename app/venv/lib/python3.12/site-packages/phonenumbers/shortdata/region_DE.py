"""Auto-generated file, do not edit by hand. DE metadata"""
from ..phonemetadata import NumberFormat, PhoneNumberDesc, PhoneMetadata

PHONE_METADATA_DE = PhoneMetadata(id='DE', country_code=None, international_prefix=None,
    general_desc=PhoneNumberDesc(national_number_pattern='[1-46-8]\\d{2,5}', possible_length=(3, 4, 5, 6)),
    toll_free=PhoneNumberDesc(national_number_pattern='11(?:[02]|6\\d{3})', example_number='110', possible_length=(3, 6)),
    emergency=PhoneNumberDesc(national_number_pattern='11[02]', example_number='110', possible_length=(3,)),
    short_code=PhoneNumberDesc(national_number_pattern='11(?:[025]|6(?:00[06]|1(?:1[167]|23))|800\\d)|22(?:044|5(?:43|80)|7700|922)|33(?:11|3[34])|44844|600\\d\\d|7(?:0\\d{3}|464)|80808|118\\d\\d', example_number='110', possible_length=(3, 4, 5, 6)),
    carrier_specific=PhoneNumberDesc(national_number_pattern='(?:33[13]|746)\\d|(?:22(?:[059]|7\\d)|(?:44|80)8|600|70\\d)\\d\\d', example_number='3310', possible_length=(4, 5, 6)),
    sms_services=PhoneNumberDesc(national_number_pattern='(?:333|746)\\d|(?:22(?:[059]|7\\d)|(?:44|80)8|600|70\\d)\\d\\d', example_number='3330', possible_length=(4, 5, 6)),
    short_data=True)

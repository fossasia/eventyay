class VatNumberCheckResult(object):
    """Result of a VAT number validation check.

    :ivar is_valid:
        Boolean value indicating if the checked VAT number was deemed to be
        valid. ``True`` if the VAT number is valid or ``False`` if the VAT
        number is positively invalid.
    :ivar log_lines:
        Check log lines.
    :ivar business_name: Optional business name retrieved for the VAT number.
    :ivar business_address: Optional address retrieved for the VAT number.
    """

    def __init__(self,
                 is_valid=None,
                 log_lines=None,
                 business_name=None,
                 business_address=None,
                 business_country_code=None):
        self.is_valid = is_valid
        self.log_lines = log_lines or []
        self.business_name = business_name
        self.business_address = business_address
        self.business_country_code = business_country_code
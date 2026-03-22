class Party(object):
    """Trading party.

    Represents either a consumer or business in a given country acting as a
    party to a transaction.

    :ivar country_code:
        Party's legal or effective country of registration or residence as an
        ISO 3166-1 alpha-2 country code.
    :type country_code: str
    :ivar is_business: Whether the part is a legal business entity.
    :type is_business: bool
    """

    def __init__(self, country_code, is_business):
        """Initialize a trading party.

        :param country_code:
            Party's legal or effective country of registration or residence as
            an ISO 3166-1 alpha-2 country code.
        :type country_code: str
        :param is_business: Whether the part is a legal business entity.
        :type is_business: bool
        """

        self.country_code = country_code
        self.is_business = is_business

    def __repr__(self):
        return '<pyvat.Party: country code = %s, is business = %r>' % (
            self.country_code, self.is_business,
        )

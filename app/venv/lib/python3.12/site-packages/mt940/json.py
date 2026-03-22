from __future__ import absolute_import
import json
import decimal
import datetime


from . import models


class JSONEncoder(json.JSONEncoder):

    def default(self, value):
        # The following types should simply be cast to strings
        str_types = (
            datetime.date,
            datetime.datetime,
            datetime.timedelta,
            datetime.tzinfo,
            decimal.Decimal,
        )

        dict_types = (
            models.Balance,
            models.Amount,
        )

        # Handle native types that should be converted to strings
        if isinstance(value, str_types):
            return str(value)

        # Handling of the Transaction objects to include the actual
        # transactions
        elif isinstance(value, models.Transactions):
            data = value.data.copy()
            data['transactions'] = value.transactions
            return data

        # If an object has a `data` attribute, return that instead of the
        # `__dict__` ro prevent loops
        elif hasattr(value, 'data'):
            return value.data

        # Handle types that have a `__dict__` containing the data (doesn't work
        # for classes using `__slots__` such as `datetime`)
        elif isinstance(value, dict_types):
            return value.__dict__

        else:  # pragma: no cover
            return json.JSONEncoder.default(self, value)

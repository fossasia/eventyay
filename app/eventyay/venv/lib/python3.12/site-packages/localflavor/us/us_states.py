"""
Misspellings/abbreviations mapping.

A mapping of state misspellings/abbreviations to normalized
abbreviations, and alphabetical lists of US states, territories,
military mail regions and non-US states to which the US provides
postal service.

This exists in this standalone file so that it's only imported into memory
when explicitly needed.
"""

import operator

from django.utils.functional import lazy
from django.utils.translation import gettext_lazy as _
from django.utils.translation import pgettext_lazy

#: The 48 contiguous states, plus the District of Columbia.
CONTIGUOUS_STATES = (
    ('AL', _('Alabama')),
    ('AZ', _('Arizona')),
    ('AR', _('Arkansas')),
    ('CA', _('California')),
    ('CO', _('Colorado')),
    ('CT', _('Connecticut')),
    ('DE', _('Delaware')),
    ('DC', _('District of Columbia')),
    ('FL', _('Florida')),
    ('GA', pgettext_lazy('US state', 'Georgia')),
    ('ID', _('Idaho')),
    ('IL', _('Illinois')),
    ('IN', _('Indiana')),
    ('IA', _('Iowa')),
    ('KS', _('Kansas')),
    ('KY', _('Kentucky')),
    ('LA', _('Louisiana')),
    ('ME', _('Maine')),
    ('MD', _('Maryland')),
    ('MA', _('Massachusetts')),
    ('MI', _('Michigan')),
    ('MN', _('Minnesota')),
    ('MS', _('Mississippi')),
    ('MO', _('Missouri')),
    ('MT', _('Montana')),
    ('NE', _('Nebraska')),
    ('NV', _('Nevada')),
    ('NH', _('New Hampshire')),
    ('NJ', _('New Jersey')),
    ('NM', _('New Mexico')),
    ('NY', _('New York')),
    ('NC', _('North Carolina')),
    ('ND', _('North Dakota')),
    ('OH', _('Ohio')),
    ('OK', _('Oklahoma')),
    ('OR', _('Oregon')),
    ('PA', _('Pennsylvania')),
    ('RI', _('Rhode Island')),
    ('SC', _('South Carolina')),
    ('SD', _('South Dakota')),
    ('TN', _('Tennessee')),
    ('TX', _('Texas')),
    ('UT', _('Utah')),
    ('VT', _('Vermont')),
    ('VA', _('Virginia')),
    ('WA', _('Washington')),
    ('WV', _('West Virginia')),
    ('WI', _('Wisconsin')),
    ('WY', _('Wyoming')),
)

#: Non contiguous states (Not connected to mainland USA)
NON_CONTIGUOUS_STATES = (
    ('AK', _('Alaska')),
    ('HI', _('Hawaii')),
)

#: Non-state territories.
US_TERRITORIES = (
    ('AS', _('American Samoa')),
    ('GU', _('Guam')),
    ('MP', _('Northern Mariana Islands')),
    ('PR', _('Puerto Rico')),
    ('VI', _('Virgin Islands')),
)

#: Military postal "states". Note that 'AE' actually encompasses
#: Europe, Canada, Africa and the Middle East.
ARMED_FORCES_STATES = (
    ('AA', _('Armed Forces Americas')),
    ('AE', _('Armed Forces Europe')),
    ('AP', _('Armed Forces Pacific')),
)

#: Non-US locations serviced by USPS (under Compact of Free
#: Association).
COFA_STATES = (
    ('FM', _('Federated States of Micronesia')),
    ('MH', _('Marshall Islands')),
    ('PW', _('Palau')),
)

#: Obsolete abbreviations (no longer US territories/USPS service, or
#: code changed).
OBSOLETE_STATES = (
    ('CM', _('Commonwealth of the Northern Mariana Islands')),  # Is now 'MP'
    ('CZ', _('Panama Canal Zone')),  # Reverted to Panama 1979
    ('PI', _('Philippine Islands')),  # Philippine independence 1946
    # Became the independent COFA states + Northern Mariana Islands 1979-1994
    ('TT', _('Trust Territory of the Pacific Islands')),
)

US_STATES = lazy(lambda: tuple(sorted(
    CONTIGUOUS_STATES + NON_CONTIGUOUS_STATES,
    key=operator.itemgetter(1))), tuple)()
"""
This docstring is not read by Sphinx, so it has been copied to
docs/localflavor/us.rst.

All US states.

This tuple is lazily generated and may not work as expected in all cases due
to tuple optimizations in the Python interpreter which do not account for
lazily generated tuples.  For example::

  US_STATES + ('XX', _('Select a State'))

should work as expected, but::

  ('XX', _('Select a State')) + US_STATES

may throw:

``TypeError: can only concatenate tuple (not "proxy") to tuple``

due to a Python optimization that causes the concatenation to occur before
US_STATES has been lazily generated.  To work around these issues, you
can use a slice index (``[:]``) to force the generation of US_STATES
before any other operations are processed by the Python interpreter::

  ('XX', _('Select a State')) + US_STATES[:]
"""

STATE_CHOICES = lazy(lambda: tuple(sorted(
    CONTIGUOUS_STATES + NON_CONTIGUOUS_STATES + US_TERRITORIES + ARMED_FORCES_STATES,
    key=operator.itemgetter(1))), tuple)()
"""
This docstring is not read by Sphinx, so it has been copied to
docs/localflavor/us.rst.

All US states and territories plus DC and military mail.

This tuple is lazily generated and may not work as expected in all cases due
to tuple optimizations in the Python interpreter which do not account for
lazily generated tuples.  For example::

  STATE_CHOICES + ('XX', _('Select a State'))

should work as expected, but::

  ('XX', _('Select a State')) + STATE_CHOICES

may throw:

``TypeError: can only concatenate tuple (not "proxy") to tuple``

due to a Python optimization that causes the concatenation to occur before
STATE_CHOICES has been lazily generated.  To work around these issues, you
can use a slice index (``[:]``) to force the generation of STATE_CHOICES
before any other operations are processed by the Python interpreter::

  ('XX', _('Select a State')) + STATE_CHOICES[:]
"""

USPS_CHOICES = lazy(lambda: tuple(sorted(
    CONTIGUOUS_STATES + NON_CONTIGUOUS_STATES + US_TERRITORIES + ARMED_FORCES_STATES + COFA_STATES,
    key=operator.itemgetter(1))), tuple)()
"""
This docstring is not read by Sphinx, so it has been copied to
docs/localflavor/us.rst.

All US Postal Service locations.

This tuple is lazily generated and may not work as expected in all cases due
to tuple optimizations in the Python interpreter which do not account for
lazily generated tuples.  For example::

  USPS_CHOICES + ('XX', _('Select a State'))

should work as expected, but::

  ('XX', _('Select a State')) + USPS_CHOICES

may throw:

``TypeError: can only concatenate tuple (not "proxy") to tuple``

due to a Python optimization that causes the concatenation to occur before
USPS_CHOICES has been lazily generated.  To work around these issues, you
can use a slice index (``[:]``) to force the generation of USPS_CHOICES
before any other operations are processed by the Python interpreter::

  ('XX', _('Select a State')) + USPS_CHOICES[:]
"""

#: Normalized versions of state names
STATES_NORMALIZED = {
    'aa': 'AA',
    'ae': 'AE',
    'ak': 'AK',
    'al': 'AL',
    'ala': 'AL',
    'alabama': 'AL',
    'alaska': 'AK',
    'ap': 'AP',
    'american samao': 'AS',
    'american samoa': 'AS',
    'ar': 'AR',
    'ariz': 'AZ',
    'arizona': 'AZ',
    'ark': 'AR',
    'arkansas': 'AR',
    'as': 'AS',
    'az': 'AZ',
    'ca': 'CA',
    'calf': 'CA',
    'calif': 'CA',
    'california': 'CA',
    'co': 'CO',
    'colo': 'CO',
    'colorado': 'CO',
    'conn': 'CT',
    'connecticut': 'CT',
    'ct': 'CT',
    'dc': 'DC',
    'de': 'DE',
    'del': 'DE',
    'delaware': 'DE',
    'deleware': 'DE',
    'district of columbia': 'DC',
    'federated states of micronesia': 'FM',
    'fl': 'FL',
    'fla': 'FL',
    'florida': 'FL',
    'fm': 'FM',
    'fsm': 'FM',
    'ga': 'GA',
    'georgia': 'GA',
    'gu': 'GU',
    'guam': 'GU',
    'hawaii': 'HI',
    'hi': 'HI',
    'ia': 'IA',
    'id': 'ID',
    'idaho': 'ID',
    'il': 'IL',
    'ill': 'IL',
    'illinois': 'IL',
    'in': 'IN',
    'ind': 'IN',
    'indiana': 'IN',
    'iowa': 'IA',
    'kan': 'KS',
    'kans': 'KS',
    'kansas': 'KS',
    'kentucky': 'KY',
    'ks': 'KS',
    'ky': 'KY',
    'la': 'LA',
    'louisiana': 'LA',
    'ma': 'MA',
    'maine': 'ME',
    'marianas islands': 'MP',
    'marianas islands of the pacific': 'MP',
    'marinas islands of the pacific': 'MP',
    'marshall islands': 'MH',
    'maryland': 'MD',
    'mass': 'MA',
    'massachusetts': 'MA',
    'massachussetts': 'MA',
    'md': 'MD',
    'me': 'ME',
    'mh': 'MH',
    'mi': 'MI',
    'mich': 'MI',
    'michigan': 'MI',
    'micronesia': 'FM',
    'minn': 'MN',
    'minnesota': 'MN',
    'miss': 'MS',
    'mississippi': 'MS',
    'missouri': 'MO',
    'mn': 'MN',
    'mo': 'MO',
    'mont': 'MT',
    'montana': 'MT',
    'mp': 'MP',
    'ms': 'MS',
    'mt': 'MT',
    'n d': 'ND',
    'n dak': 'ND',
    'n h': 'NH',
    'n j': 'NJ',
    'n m': 'NM',
    'n mex': 'NM',
    'nc': 'NC',
    'nd': 'ND',
    'ne': 'NE',
    'neb': 'NE',
    'nebr': 'NE',
    'nebraska': 'NE',
    'nev': 'NV',
    'nevada': 'NV',
    'new hampshire': 'NH',
    'new jersey': 'NJ',
    'new mexico': 'NM',
    'new york': 'NY',
    'nh': 'NH',
    'nj': 'NJ',
    'nm': 'NM',
    'nmex': 'NM',
    'north carolina': 'NC',
    'north dakota': 'ND',
    'northern mariana islands': 'MP',
    'nv': 'NV',
    'ny': 'NY',
    'oh': 'OH',
    'ohio': 'OH',
    'ok': 'OK',
    'okla': 'OK',
    'oklahoma': 'OK',
    'or': 'OR',
    'ore': 'OR',
    'oreg': 'OR',
    'oregon': 'OR',
    'pa': 'PA',
    'palau': 'PW',
    'penn': 'PA',
    'pennsylvania': 'PA',
    'pr': 'PR',
    'puerto rico': 'PR',
    'pw': 'PW',
    'republic of palau': 'PW',
    'republic of the marshall islands': 'MH',
    'rhode island': 'RI',
    'ri': 'RI',
    's dak': 'SD',
    'sc': 'SC',
    'sd': 'SD',
    'sdak': 'SD',
    'south carolina': 'SC',
    'south dakota': 'SD',
    'tenn': 'TN',
    'tennessee': 'TN',
    'territory of hawaii': 'HI',
    'tex': 'TX',
    'texas': 'TX',
    'tn': 'TN',
    'tx': 'TX',
    'us virgin islands': 'VI',
    'usvi': 'VI',
    'ut': 'UT',
    'utah': 'UT',
    'va': 'VA',
    'vermont': 'VT',
    'vi': 'VI',
    'viginia': 'VA',
    'virgin islands': 'VI',
    'virgina': 'VA',
    'virginia': 'VA',
    'vt': 'VT',
    'w va': 'WV',
    'wa': 'WA',
    'wash': 'WA',
    'washington': 'WA',
    'west virginia': 'WV',
    'wi': 'WI',
    'wis': 'WI',
    'wisc': 'WI',
    'wisconsin': 'WI',
    'wv': 'WV',
    'wva': 'WV',
    'wy': 'WY',
    'wyo': 'WY',
    'wyoming': 'WY',
}

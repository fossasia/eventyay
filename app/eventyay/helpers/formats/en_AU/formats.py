# Date according to https://docs.djangoproject.com/en/dev/ref/templates/builtins/#date
SHORT_DATE_FORMAT = 'd/m/Y'
SHORT_DATETIME_FORMAT = 'd/m/Y H:i'
TIME_FORMAT = 'H:i'
WEEK_FORMAT = '\\W W, o'
WEEK_DAY_FORMAT = 'D, M jS'

DATE_INPUT_FORMATS = [
    '%d/%m/%Y',
    '%d/%m/%y',
    '%Y-%m-%d',
]
TIME_INPUT_FORMATS = [
    '%H:%M:%S',  # '14:30:59'
    '%H:%M:%S.%f',  # '14:30:59.000200'
    '%H:%M',  # '14:30'
]

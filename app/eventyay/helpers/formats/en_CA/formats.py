# Date according to https://docs.djangoproject.com/en/dev/ref/templates/builtins/#date
SHORT_DATE_FORMAT = 'Y-m-d'
SHORT_DATETIME_FORMAT = 'Y-m-d H:i'
TIME_FORMAT = 'H:i'
WEEK_FORMAT = '\\W W, o'
WEEK_DAY_FORMAT = 'D, M jS'

DATE_INPUT_FORMATS = [
    '%Y-%m-%d',
    '%d/%m/%Y',
    '%m/%d/%Y',
]
TIME_INPUT_FORMATS = [
    '%H:%M:%S',  # '14:30:59'
    '%H:%M:%S.%f',  # '14:30:59.000200'
    '%H:%M',  # '14:30'
]

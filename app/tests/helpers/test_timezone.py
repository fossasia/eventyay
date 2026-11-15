from eventyay.helpers.timezone import format_timezone_name


def test_format_timezone_name_replaces_underscores_only_for_display():
    timezone = 'Asia/Ho_Chi_Minh'

    assert format_timezone_name(timezone) == 'Asia/Ho Chi Minh'
    assert timezone == 'Asia/Ho_Chi_Minh'


def test_format_timezone_name_handles_empty_values():
    assert format_timezone_name(None) == ''
    assert format_timezone_name('UTC') == 'UTC'

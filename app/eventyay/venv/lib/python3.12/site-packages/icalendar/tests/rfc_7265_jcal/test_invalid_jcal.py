"""We would like to have certain errors for invalid JCal."""

from json import JSONDecodeError

import pytest

from icalendar import (
    Calendar,
    Component,
    JCalParsingError,
    Parameters,
    vDate,
    vDatetime,
    vDDDTypes,
    vDuration,
    vPeriod,
    vTime,
)
from icalendar.prop import vCategory, vMonth, vRecur, vSkip


def test_invalid_json():
    """JSON can be invalid"""
    with pytest.raises(JSONDecodeError):
        Component.from_jcal("")


@pytest.fixture(params=[[], {}, None, 1, 1.3])
def str_expected(request):
    """Return everything else"""
    return request.param


@pytest.fixture(params=["a", {}, None, 1, 1.3])
def list_expected(request):
    """Return everything else"""
    return request.param


@pytest.fixture(params=["a", [], None, 1, 1.3])
def object_expected(request):
    """Return everything else"""
    return request.param


@pytest.fixture(params=["a", [], {}, None, 1.3])
def int_expected(request):
    """Return everything else"""
    return request.param


@pytest.fixture(params=["a", [], {}, None, 1])
def float_expected(request):
    """Return everything else"""
    return request.param


@pytest.fixture(params=[[], {}, None, [None], [{}], [[]]])
def parameter_value_expected(request):
    """Return everything else"""
    return request.param


@pytest.mark.parametrize("length", [0, 1, 2, 4, 5])
def test_component_is_too_short_or_too_long(length):
    """Test that a component has not enough values.

    See https://github.com/collective/icalendar/pull/979/#discussion_r2529703982

    """
    with pytest.raises(
        JCalParsingError,
        match=r"in Component: A component must be a list with 3 items\.",
    ):
        Component.from_jcal(["vevent", [], [], [], []][:length])


def test_invalid_component_type(list_expected):
    """We expect a list for components."""
    if isinstance(list_expected, str):
        return  # skip JSON
    with pytest.raises(
        JCalParsingError, match=r"Component: A component must be a list with 3 items\."
    ):
        Component.from_jcal(list_expected)
    with pytest.raises(
        JCalParsingError,
        match=r"\[2\]\[0\] in Calendar: A component must be a list with 3 items\.",
    ):
        Component.from_jcal(["VCALENDAR", [], [list_expected]])


def test_invalid_component_name(str_expected):
    """Test the component name."""
    with pytest.raises(
        JCalParsingError, match=r"\[0\] in Component: The name must be a string\."
    ):
        Component.from_jcal([str_expected, [], []])


def test_invalid_component_properties(list_expected):
    """Test the component properties."""
    with pytest.raises(
        JCalParsingError, match=r"\[1\] in Alarm: The properties must be a list\."
    ):
        Component.from_jcal(["valarm", list_expected, []])


def test_invalid_component_subcomponents(list_expected):
    """Test the component subcomponents."""
    with pytest.raises(
        JCalParsingError, match=r"\[2\] in Todo: The subcomponents must be a list\."
    ):
        Component.from_jcal(["vtodo", [], list_expected])


@pytest.mark.parametrize("i", [0, 3, 10])
def test_invalid_component_property(list_expected, i):
    """Test the component properties."""
    with pytest.raises(
        JCalParsingError,
        match=rf"\[1\]\[{i}\] in Event: The property must be a list with at least 4 items\.",
    ):
        Component.from_jcal(
            ["vevent", [["x-x", {}, "unknown", ""]] * i + [list_expected], []]
        )


@pytest.mark.parametrize("length", [0, 1, 2, 3])
def test_property_too_short(length, v_prop_example, v_prop):
    """The example is too short."""
    jcal = v_prop_example.to_jcal("name")[:length]
    with pytest.raises(
        JCalParsingError,
        match=rf"in {v_prop.__name__}: The property must be a list with at least 4 items\.",
    ):
        v_prop.from_jcal(jcal)

    with pytest.raises(
        JCalParsingError,
        match=r"in Parameters: The property must be a list with at least 4 items\.",
    ):
        Parameters.from_jcal_property(jcal)


def test_property_name(v_prop_example, v_prop, str_expected):
    """The name is a string."""
    jcal = v_prop_example.to_jcal("name")
    jcal[0] = str_expected
    with pytest.raises(
        JCalParsingError,
        match=rf"\[0\] in {v_prop.__name__}: The name must be a string\.",
    ):
        v_prop.from_jcal(jcal)


def test_property_params(v_prop_example, v_prop, object_expected):
    """The name is a string."""
    jcal = v_prop_example.to_jcal("name")
    jcal[1] = object_expected
    with pytest.raises(
        JCalParsingError,
        match=rf"\[1\] in {v_prop.__name__}: The parameters must be a mapping\.",
    ):
        v_prop.from_jcal(jcal)
    with pytest.raises(
        JCalParsingError,
        match=r"\[1\] in Parameters: The parameters must be a mapping\.",
    ):
        Parameters.from_jcal_property(jcal)


def test_property_type(v_prop_example, v_prop, str_expected):
    """The name is a string."""
    jcal = v_prop_example.to_jcal("name")
    jcal[2] = str_expected
    with pytest.raises(
        JCalParsingError,
        match=rf"\[2\] in {v_prop.__name__}: The VALUE parameter must be a string\.",
    ):
        v_prop.from_jcal(jcal)


@pytest.mark.parametrize("index", [0, 3])
def test_property_too_short_in_component(v_prop_example, v_prop, index):
    """The example is too short."""
    jcal = v_prop_example.to_jcal("X-PROP")
    component = [
        "vcalendar",
        [["X-PROP-2", {}, "unknown", ""]] * index + [jcal[:2]],
        [],
    ]
    print(jcal)
    with pytest.raises(
        JCalParsingError,
        match=rf"\[1\]\[{index}\] in Calendar: The property must be a list with at least 4 items\.",
    ):
        Component.from_jcal(component)


def test_parameters_keys(str_expected):
    """The parameter keys should be all strings."""
    if str_expected in ([], {}):
        return  # TypeError: unhashable type
    with pytest.raises(
        JCalParsingError,
        match=r"in Parameters: All parameter names must be strings\.",
    ):
        Parameters.from_jcal_property(["", {str_expected: "value"}, "", ""])


@pytest.mark.parametrize("key", ["a", "key"])
def test_values_allowed_in_parameters(parameter_value_expected, key):
    """The parameter keys should be all strings."""
    with pytest.raises(
        JCalParsingError,
        match=rf'\[1\]\["{key}"\] in Parameters: Parameter values must be a string, integer or float or a list of those\.',
    ):
        Parameters.from_jcal_property(["", {key: parameter_value_expected}, "", ""])


def test_failing_example_delegated_to(calendars):
    """Check the failing example."""
    calendar: Calendar = calendars.rfc_7256_multi_value_parameters
    jcal = calendar.to_jcal()
    delegated_to = jcal[2][0][1][0][1]["delegated-to"]
    assert delegated_to == [
        "mailto:jdoe@example.com",
        "mailto:jqpublic@example.com",
    ]
    assert all(type(item) is str for item in delegated_to)


@pytest.mark.parametrize(
    ("v_prop", "ty", "message", "value"),
    [
        (vDatetime, "date-time", r"Cannot parse date-time\.", ""),
        (vDate, "date", r"Cannot parse date\.", ""),
        (vTime, "time", r"Cannot parse time\.", ""),
        (vTime, "time", r"Cannot parse time\.", "asd"),
        (vDuration, "duration", r"Cannot parse duration\.", "PXD"),
        (
            vDDDTypes,
            "date-time",
            r"Cannot parse date, time, date-time, duration, or period\.",
            "",
        ),
    ],
)
def test_date_time_parsing_errors(v_prop, message, ty, value):
    """An empty datetime should raise an error."""
    with pytest.raises(
        JCalParsingError,
        match=rf"\[3\] in {v_prop.__name__}: {message}",
    ):
        v_prop.from_jcal(["dt", {}, ty, value])


@pytest.mark.parametrize(
    "v_prop",
    [
        vDuration,
        vDate,
        vTime,
        vDatetime,
        vDDDTypes,
    ],
)
def test_wrong_type(v_prop, str_expected):
    """Passing an int or float where a string is expected should raise an error."""
    if isinstance(str_expected, list) and v_prop is vDDDTypes:
        return  # skip vPeriod
    with pytest.raises(
        JCalParsingError,
        match=rf"\[3\] in {v_prop.__name__}: The value must be a string\.",
    ):
        v_prop.from_jcal(["dt", {}, "date-time", str_expected])


def test_vPeriod_wrong_type(str_expected):
    """Passing an int or float where a string is expected should raise an error."""
    with pytest.raises(
        JCalParsingError,
        match=r"\[3\]\[0\] in .*: The value must be a string\.",
    ):
        vPeriod.from_jcal(
            ["rdate", {}, "period", [str_expected, "2024-01-01T00:00:00Z"]]
        )
    with pytest.raises(
        JCalParsingError,
        match=r"\[3\]\[1\] in .*: The value must be a string\.",
    ):
        vPeriod.from_jcal(
            ["rdate", {}, "period", ["2024-01-01T00:00:00Z", str_expected]]
        )


def test_vPeriod_too_short():
    """A period with too few items should raise an error."""
    with pytest.raises(
        JCalParsingError,
        match=r"\[3\] in vPeriod: A period must be a list with exactly 2 items\.",
    ):
        vPeriod.from_jcal(["rdate", {}, "period", ["2024-01-01T00:00:00Z"]])


def test_vPeriod_too_long():
    """A period with too many items should raise an error."""
    with pytest.raises(
        JCalParsingError,
        match=r"\[3\] in vPeriod: A period must be a list with exactly 2 items\.",
    ):
        vPeriod.from_jcal(
            [
                "rdate",
                {},
                "period",
                ["2024-01-01T00:00:00Z", "2024-01-02T00:00:00Z", "extra"],
            ]
        )


def test_vPeriod_expects_date_time_as_start():
    """vPeriod expects date-time as start but we hand in a duration."""
    with pytest.raises(
        JCalParsingError,
        match=r"\[3\]\[0\] in .*: Cannot parse date-time\.",
    ):
        vPeriod.from_jcal(
            [
                "rdate",
                {},
                "period",
                ["P1D", "2024-01-02T00:00:00Z"],
            ]
        )


def test_vPeriod_expects_date_time_or_duration_as_second_item():
    """vPeriod expects date-time or duration as second item but we hand in a date."""
    with pytest.raises(
        JCalParsingError,
        match=r"\[3\]\[1\] in .*: Cannot parse date-time or duration\.",
    ):
        vPeriod.from_jcal(
            [
                "rdate",
                {},
                "period",
                ["2024-01-01T00:00:00", "2024-01-02"],
            ]
        )


@pytest.mark.parametrize("index", [0, 4])
def test_invalid_category_type(str_expected, index):
    """The name is a string."""
    with pytest.raises(
        JCalParsingError,
        match=rf"\[{index + 3}\] in vCategory: The value must be a string\.",
    ):
        vCategory.from_jcal(["categories", {}, "text"] + [""] * index + [str_expected])


def test_validation_of_list():
    """Check the list validation."""
    JCalParsingError.validate_list_type(["a", "b", "c"], str, "test", ["path"])
    with pytest.raises(
        JCalParsingError,
        match=r"\[3\]\[1\] in test: Each item in the list must be a string\.",
    ):
        JCalParsingError.validate_list_type(["a", 1, "c"], str, "test", path=3)


def test_recurrence_rule_must_be_mapping(object_expected):
    """The recurrence rule must be a mapping."""
    with pytest.raises(
        JCalParsingError,
        match=r"\[3\] in vRecur: The recurrence rule must be a mapping with string keys\.",
    ):
        vRecur.from_jcal(["rrule", {}, "recur", object_expected])


def test_recurrence_rule_must_be_mapping_with_str(str_expected):
    """The recurrence rule must be a mapping."""
    if isinstance(str_expected, (dict, list)):
        return  # skip unhashable type
    with pytest.raises(
        JCalParsingError,
        match=r"\[3\] in vRecur: The recurrence rule must be a mapping with string keys\.",
    ):
        vRecur.from_jcal(["rrule", {}, "recur", {str_expected: 1}])


@pytest.mark.parametrize(
    "key",
    [
        "COUNT",
        "INTERVAL",
        "BYSECOND",
        "BYMINUTE",
        "BYHOUR",
        "BYWEEKNO",
        "BYMONTHDAY",
        "BYYEARDAY",
    ],
)
@pytest.mark.parametrize("as_list", [False, True])
def test_int_parameters(int_expected, key, as_list):
    """The integer parameters must be integers."""
    correct_value = 4
    if as_list:
        int_expected = [int_expected]
        correct_value = [4]
    # parse correct value
    recur = vRecur.from_jcal(["rrule", {}, "recur", {key: correct_value}])
    assert recur[key] == correct_value or recur[key] == [correct_value]
    if int_expected == []:
        return
    # parse bad value
    with pytest.raises(
        JCalParsingError,
        match=f'\\[3\\]\\["{key}"\\](?:\\[0\\])? in vInt: The value must be an integer.',
    ):
        vRecur.from_jcal(["rrule", {}, "recur", {key: int_expected}])


@pytest.mark.parametrize("valid", [1, "1", "1L"])
def test_parse_jcal_value_month(valid):
    """Test parsing of vMonth jCal values."""
    month = vMonth.parse_jcal_value(valid)
    assert month == 1
    assert month.leap == (valid == "1L")


@pytest.mark.parametrize("invalid", ["abc", "", 1.5, [], {}, "1LL"])
def test_parse_jcal_value_month_invalid(invalid):
    """Test parsing of vMonth jCal values."""
    with pytest.raises(
        JCalParsingError,
        match=r"in vMonth: The value must be a string or an integer\.",
    ):
        vMonth.parse_jcal_value(invalid)


def test_skip():
    """The skip parameter works."""
    assert vSkip.parse_jcal_value("OMIT") is vSkip.OMIT
    with pytest.raises(
        JCalParsingError,
        match=r"in vSkip: The value must be a valid skip value\.",
    ):
        vSkip.parse_jcal_value("INVALID")


def test_frequency():
    """The FREQ parameter must be valid."""
    # parse correct value
    recur = vRecur.from_jcal(["rrule", {}, "recur", {"FREQ": "DAILY"}])
    assert recur["FREQ"] == "DAILY"
    # parse bad value
    with pytest.raises(
        JCalParsingError,
        match=r'\[3\]\["FREQ"\] in vFrequency: The value must be a valid frequency\.',
    ):
        vRecur.from_jcal(["rrule", {}, "recur", {"FREQ": "INVALID"}])

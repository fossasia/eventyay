"""Check some module consistency."""

from datetime import date, datetime, time, timedelta

import pytest

import icalendar
from icalendar import Parameters, prop, vDDDLists, vDDDTypes
from icalendar.tests.data import PARAMETER_NAMES


def test_all_propeties_are_exported(v_prop_name):
    """icalendar.prop should export all these properties."""
    assert v_prop_name in prop.__all__
    assert v_prop_name in icalendar.__all__
    assert getattr(prop, v_prop_name, None) is not None
    assert getattr(icalendar, v_prop_name, None) is not None


def test_all_properties_have_an_examples_method(v_prop):
    """All properties have a class method that returns a list of examples."""
    examples = v_prop.examples()
    assert isinstance(examples, list), "We expect a list of examples."
    assert len(examples) > 0, "We have examples."
    assert all(isinstance(example, v_prop) for example in examples), (
        "All examples should be of that type."
    )
    assert v_prop.__name__ in v_prop.examples.__doc__.splitlines()[0], (
        "type is in docstring"
    )


def test_all_properties_are_part_of_the_union_type(v_prop):
    """Check the union type captures all vProperty instances."""
    assert v_prop in prop.VPROPERTY.__args__


@pytest.mark.parametrize("no_prop", PARAMETER_NAMES)
def test_if_not_part_of_properties_they_are_not_included_in_the_type(no_prop):
    """If these are not properties rather parameters, do not include them."""
    assert no_prop not in prop.VPROPERTY.__args__


default_value_map = {
    prop.vBoolean: "BOOLEAN",
    prop.vCalAddress: "CAL-ADDRESS",
    prop.vCategory: "TEXT",
    prop.vDate: "DATE",
    prop.vDatetime: "DATE-TIME",
    prop.vDuration: "DURATION",
    prop.vFloat: "FLOAT",
    prop.vInt: "INTEGER",
    prop.vPeriod: "PERIOD",
    prop.vRecur: "RECUR",
    prop.vText: "TEXT",
    prop.vTime: "TIME",
    prop.vUTCOffset: "UTC-OFFSET",
    prop.vUri: "URI",
    prop.vBinary: "BINARY",
    prop.vGeo: "FLOAT",
}


@pytest.mark.parametrize(("v_prop", "default_value"), list(default_value_map.items()))
def test_get_default_value(v_prop_example: prop.VPROPERTY, default_value: str):
    """Check the default value of all properties."""
    del v_prop_example.VALUE
    assert v_prop_example.VALUE == default_value
    assert "VALUE" not in v_prop_example.params


def test_set_value(v_prop_example):
    """Test setting the VALUE parameter."""
    v_prop_example.VALUE = "X-OTHER-VALUE"
    assert v_prop_example.VALUE == "X-OTHER-VALUE"
    assert v_prop_example.params.value == "X-OTHER-VALUE"


def test_delete_the_set_value(v_prop_example, v_prop):
    """The value is defaulting after delete."""
    v_prop_example.VALUE = "X-VALUE"
    del v_prop_example.VALUE
    assert v_prop_example.VALUE != "X-VALUE"
    if v_prop in default_value_map:
        assert v_prop_example.VALUE == default_value_map[v_prop], (
            "deleted value defaults"
        )


@pytest.mark.parametrize("v_prop", [vDDDLists, vDDDTypes])
@pytest.mark.parametrize(
    ("dt", "value"),
    [
        (datetime(2018, 1, 1), "DATE-TIME"),
        (date(2018, 1, 1), "DATE"),
        (time(1, 1), "TIME"),
        (timedelta(1, 1), "DURATION"),
    ],
)
def test_dt_value(v_prop, dt, value):
    """Check that the VALUE parameter is correctly determined."""
    assert v_prop(dt).VALUE == value


def test_special_case_no_dts():
    """If the list is empty, we still need a value."""
    assert vDDDLists([]).VALUE == "DATE-TIME"


def special_case_period():
    """Check PERIOD for vDDDLists and vDDDTypes."""
    assert vDDDLists([(datetime(2018, 1, 1), timedelta(1, 1))]).VALUE == "PERIOD"
    assert vDDDTypes((datetime(2018, 1, 1), timedelta(1, 1))).VALUE == "PERIOD"


def test_value_parameter_does_not_turn_up_in_jcal():
    """The VALUE parameter should not turn up if set."""
    params = Parameters()
    params["VALUE"] = "DATE-TIME"
    assert params.to_jcal() == {}


def test_value_is_always_uppercase(v_prop_example):
    """The VALUE parameter should always be uppercase."""
    v_prop_example.VALUE = "unknown"
    assert v_prop_example.VALUE == "UNKNOWN"


def test_setting_the_value_turns_it_uppercase():
    """The VALUE parameter should always be uppercase."""
    parameters = Parameters()
    parameters.value = "unknown"
    assert parameters.value == "UNKNOWN"


def test_default_value_is_always_uppercase():
    """The default value should always be uppercase."""
    pytest.skip("TODO at a later stage when the __init__ function is implemented.")
    parameters = Parameters({"VALUE": "unknown1"})
    assert parameters.value == "UNKNOWN1"
    assert parameters["VALUE"] == "UNKNOWN1"


@pytest.mark.parametrize("attribute", ["VALUE", "to_jcal", "to_ical"])
def test_common_methods(v_prop, attribute):
    """Check that common functionality is provided by all of them."""
    assert hasattr(v_prop, attribute), (
        f'{v_prop.__name__} is missing a function or property named "{attribute}".'
    )


def test_all_possible_value_types_are_listed(types_factory):
    """Check that all values types added are also part of the TypesFactory."""
    for value in types_factory.values():
        assert value in prop.VPROPERTY.__args__, (
            f"The value type {value} is not part of VPROPERTY."
        )
        assert value in types_factory.all_types, (
            f"The value type {value} is not part of TypesFactory."
        )


def test_all_value_types_are_in_the_factory(v_prop, types_factory):
    """Check that all vProperty types are part of the TypesFactory."""
    assert v_prop in types_factory.all_types, (
        f"The value type {v_prop} is not part of TypesFactory.all_types."
    )


def test_an_new_component_class_is_registered(component_factory):
    """Check that the result is always the same."""
    assert component_factory.get_component_class(
        "VCUSTOM"
    ) is component_factory.get_component_class("VCUSTOM")

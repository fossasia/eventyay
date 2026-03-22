"""Test the new property types UID and XML-REFERENCE.

- creation
- parameters
- serialization
- deserialization
- attributes
"""

import pytest

from icalendar import Calendar, Event, vUid, vUri, vXmlReference


@pytest.fixture(
    params=[
        "123e4567-e89b-12d3-a456-426614174000",
        "550e8400-e29b-41d4-a716-446655440000",
    ]
)
def uid(request):
    return request.param


@pytest.fixture(
    params=[
        "https://example.com/events",
        "https://example.com/tasks/01234567-abcd1234.ics",
    ]
)
def uri(request):
    return request.param


@pytest.fixture(
    params=[
        (
            "https://example.com/xmlDocs/bidFramework.xml#xpointer(descendant::CostStruc/range-to(following::CostStrucEND[1]))",
            "descendant::CostStruc/range-to(following::CostStrucEND[1])",
        ),
        (
            "https://www.w3.org/TR/2003/REC-xptr-framework-20030325/#xpointer(id('r%C3%A9sum%C3%A9'))",
            "id('résumé')",
        ),
    ]
)
def xml_reference(request):
    return request.param


def test_uid_creation(uid):
    """Test creation of UID property."""
    uid_prop = vUid(uid)
    assert repr(uid_prop) == f"vUid({uid!r})"
    assert uid_prop.ical_value == uid
    assert uid_prop.uid == uid
    assert_default_parameters(uid_prop)


def test_uid_new(test_uid):
    """The new uid should be tested."""
    uid_prop = vUid.new()
    assert uid_prop.uid == test_uid
    assert_default_parameters(uid_prop)
    assert uid_prop.VALUE == "UID"


def test_vUri_creation(uri):
    """Test creation of a URI property."""
    uri_prop = vUri(uri)
    assert str(uri_prop) == uri
    assert uri_prop.ical_value == uri
    assert uri_prop.uri == uri
    assert_default_parameters(uri_prop)
    assert uri_prop.VALUE == "URI"


def test_vXmlReference_creation(xml_reference):
    """Test creation of a URI property."""
    uri, x_pointer = xml_reference
    xml_prop = vXmlReference(uri)
    assert str(xml_prop) == uri
    assert xml_prop.ical_value == uri
    assert xml_prop.uri == uri
    assert_default_parameters(xml_prop)
    assert xml_prop.x_pointer == x_pointer
    assert xml_prop.VALUE == "XML-REFERENCE"


def assert_default_parameters(prop):
    """Test an empty property."""
    assert prop.LABEL is None
    assert prop.LANGUAGE is None
    assert prop.FMTTYPE is None
    assert prop.LINKREL is None
    assert repr(prop).startswith(prop.__class__.__name__ + "(")
    assert repr(prop).endswith(")")
    assert prop.params.value is None
    assert prop.params.get("VALUE") is None


@pytest.mark.parametrize("no_x_pointer", ["", "asd)", "xpointer(id('r%C3%A9sum%C3%A9'"])
def test_not_x_pointer(no_x_pointer):
    """Test that the x_pointer throws a value error."""
    xml = vXmlReference("http://asd#" + no_x_pointer)
    assert xml.x_pointer is None


mark_valid_values = pytest.mark.parametrize(
    ("name", "value"),
    [
        ("LABEL", None),
        ("LABEL", "Venue"),
        ("LANGUAGE", None),
        ("LANGUAGE", "de"),
        ("LANGUAGE", "en-gb"),
        ("LINKREL", None),
        ("LINKREL", "SOURCE"),
        ("LINKREL", "https://example.com/linkrel/derivedFrom"),
        ("LINKREL", "icon"),
        ("FMTTYPE", None),
        ("FMTTYPE", "text/html"),
    ],
)


def vUri_example():
    """New example instance."""
    return vUri("http://example.com")


def vXmlReference_example():
    """New example instance."""
    return vXmlReference("http://example.com")


mark_new_prop = pytest.mark.parametrize(
    "new_prop", [vUri_example, vUid.new, vXmlReference_example]
)


@mark_new_prop
@mark_valid_values
def test_set_attributes(new_prop, name, value):
    """Set the values and test"""
    prop = new_prop()
    assert hasattr(prop, name)
    setattr(prop, name, value)
    print(prop.params)
    assert getattr(prop, name) == value
    if value is None:
        assert name not in prop.params
    else:
        assert prop.params[name] == value


@mark_new_prop
@mark_valid_values
def test_delete_attribute_setting_to_none(new_prop, name, value):
    """The attribute can be deleted by setting to None."""
    prop = new_prop()
    setattr(prop, name, value)
    setattr(prop, name, None)
    assert name not in prop.params
    assert getattr(prop, name) is None


@mark_new_prop
@mark_valid_values
def test_delete_attribute(new_prop, name, value):
    """The attribute can be deleted."""
    prop = new_prop()
    setattr(prop, name, value)
    delattr(prop, name)
    assert name not in prop.params
    assert getattr(prop, name) is None


def test_parse_example_calendar(calendars):
    """We should make sure that examples from the RFC work."""
    calendar: Calendar = calendars.rfc_9253_examples
    event = calendar.events[0]
    links = event.links
    assert len(links) == 3
    assert links[0].uri == "https://example.com/events"
    assert links[0].LINKREL == "SOURCE"
    assert links[0].FMTTYPE is None
    assert links[0].LABEL == "Venue"
    assert isinstance(links[0], vUri)

    assert links[1].uri == "https://example.com/tasks/01234567-abcd1234.ics"
    assert links[1].LINKREL == "https://example.com/linkrel/derivedFrom"
    assert links[1].FMTTYPE is None
    assert links[1].LABEL is None
    assert isinstance(links[1], vUri)

    assert (
        links[2].xml_reference
        == "https://example.com/xmlDocs/bidFramework.xml#xpointer(descendant::CostStruc/range-to(following::CostStrucEND[1]))"
    )
    assert links[2].LINKREL == "https://example.com/linkrel/costStructure"
    assert links[2].FMTTYPE is None
    assert links[2].LABEL is None
    assert isinstance(links[2], vXmlReference)


def test_parse_uid_example(calendars):
    """Parse the UID type."""
    calendar: Calendar = calendars.rfc_9253_examples
    event = calendar.events[1]
    links = event.links
    assert len(links) == 1
    assert links[0].uid == "links-rfc-9253-section-8.2"
    assert links[0].LINKREL == "REFERENCE"
    assert links[0].FMTTYPE is None
    assert links[0].LABEL is None
    assert isinstance(links[0], vUid)


def test_linkrel_is_always_quoted():
    """Test that the LINKREL is always quoted."""
    link = vUri("https://example.com", params={"LINKREL": "SOURCE"})
    event = Event()
    event.links = [link]
    ical = event.to_ical().decode()
    assert 'LINKREL="SOURCE"' in ical

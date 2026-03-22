"""Tests for custom component parsing and handling.

Custom components include:
- X-Components (vendor-specific, starting with X-)
- IANA-Components (registered but not in RFC 5545)
- Any unrecognized component names

According to RFC 5545:
- Applications MUST ignore custom components they don't recognize
- Applications SHOULD NOT silently drop components (data loss prevention)

icalendar preserves all custom components through dynamic component creation.
"""

from icalendar import Calendar, Component, Event
from icalendar.cal.component_factory import ComponentFactory


class TestComponentFactory:
    """Test ComponentFactory's dynamic component creation."""

    def test_create_custom_component_class(self):
        """Factory creates component classes for unknown names."""
        factory = ComponentFactory()
        my_component_class = factory.get_component_class("My-Component")
        assert my_component_class.name == "MY-COMPONENT"
        assert my_component_class.__name__ == "MyComponent"

    def test_custom_component_inherits_from_component(self):
        """Dynamically created components inherit from Component."""
        factory = ComponentFactory()
        custom_class = factory.get_component_class("X-CUSTOM")
        assert issubclass(custom_class, Component)

    def test_factory_caches_component_classes(self):
        """Factory returns same class for repeated requests."""
        factory = ComponentFactory()
        class1 = factory.get_component_class("X-VENDOR")
        class2 = factory.get_component_class("X-VENDOR")
        assert class1 is class2

    def test_sanitizes_component_names(self):
        """Factory sanitizes non-alphanumeric characters in names."""
        factory = ComponentFactory()
        component_class = factory.get_component_class("X-MY-COMPONENT")
        # Hyphens removed from class name, but preserved in .name
        assert component_class.__name__ == "XMYCOMPONENT"
        assert component_class.name == "X-MY-COMPONENT"


class TestCustomComponentWithComponentFromIcal:
    """Test parsing custom components using Component.from_ical()."""

    def test_parse_standalone_custom_component(self, calendars):
        """Parse a standalone custom component (issue #178)."""
        # MYCOMP is not a standard RFC 5545 component
        calendar = calendars.issue_178_component_with_invalid_name_represented
        # Should parse without error
        assert calendar.to_ical() == calendar.raw_ics

    def test_custom_component_preserves_name(self):
        """Custom component name is preserved."""
        ics_data = b"BEGIN:X-MYCOMPONENT\r\nEND:X-MYCOMPONENT\r\n"
        comp = Component.from_ical(ics_data)
        assert comp.name == "X-MYCOMPONENT"

    def test_custom_component_with_properties(self):
        """Custom components can have properties."""
        ics_data = b"""BEGIN:X-VENDOR
SUMMARY:Vendor Component
X-VENDOR-PROP:proprietary value
UID:vendor-123
END:X-VENDOR
"""
        comp = Component.from_ical(ics_data)
        assert comp.name == "X-VENDOR"
        assert comp["SUMMARY"] == "Vendor Component"
        assert comp["X-VENDOR-PROP"] == "proprietary value"
        assert comp["UID"] == "vendor-123"

    def test_custom_component_round_trip(self):
        """Custom components survive round-trip parsing."""
        original = b"BEGIN:X-TEST\r\nSUMMARY:Test\r\nEND:X-TEST\r\n"
        comp = Component.from_ical(original)
        regenerated = comp.to_ical()
        assert b"BEGIN:X-TEST" in regenerated
        assert b"SUMMARY:Test" in regenerated
        assert b"END:X-TEST" in regenerated

    def test_custom_component_can_contain_standard_components(self, calendars):
        """Custom component can contain standard components (issue #178)."""
        # MYCOMPTOO contains a VEVENT
        calendar = calendars.issue_178_custom_component_contains_other
        assert calendar.to_ical() == calendar.raw_ics

    def test_parse_custom_component_containing_event(self):
        """Parse custom component containing VEVENT."""
        ics_data = b"""BEGIN:X-CONTAINER
SUMMARY:Container
BEGIN:VEVENT
UID:event-1
DTSTART:20240101T120000Z
SUMMARY:Event inside custom
END:VEVENT
END:X-CONTAINER
"""
        container = Component.from_ical(ics_data)
        assert container.name == "X-CONTAINER"
        assert len(container.subcomponents) == 1
        event = container.subcomponents[0]
        assert event.name == "VEVENT"
        assert event["UID"] == "event-1"
        assert event["SUMMARY"] == "Event inside custom"


class TestCustomComponentWithCalendarFromIcal:
    """Test parsing custom components using Calendar.from_ical()."""

    def test_calendar_with_custom_component(self, calendars):
        """Calendar can contain custom components (issue #178)."""
        # VCALENDAR with UNKNOWN component
        calendar = calendars.issue_178_custom_component_inside_other
        assert calendar.to_ical() == calendar.raw_ics

    def test_parse_calendar_containing_custom_component(self):
        """Parse VCALENDAR containing custom component."""
        ics_data = b"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//EN
BEGIN:X-CUSTOM
UID:custom-1
SUMMARY:Custom component in calendar
END:X-CUSTOM
END:VCALENDAR
"""
        cal = Calendar.from_ical(ics_data)
        assert len(cal.subcomponents) == 1
        custom = cal.subcomponents[0]
        assert custom.name == "X-CUSTOM"
        assert custom["UID"] == "custom-1"

    def test_calendar_with_mixed_standard_and_custom_components(self):
        """Calendar can mix standard and custom components."""
        ics_data = b"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//EN
BEGIN:VEVENT
UID:event-1
DTSTART:20240101T120000Z
SUMMARY:Standard event
END:VEVENT
BEGIN:X-VENDOR
UID:vendor-1
X-PROP:value
END:X-VENDOR
BEGIN:VTODO
UID:todo-1
SUMMARY:Standard todo
END:VTODO
END:VCALENDAR
"""
        cal = Calendar.from_ical(ics_data)
        assert len(cal.subcomponents) == 3

        # Verify component types
        names = [comp.name for comp in cal.subcomponents]
        assert "VEVENT" in names
        assert "X-VENDOR" in names
        assert "VTODO" in names

    def test_custom_component_round_trip_in_calendar(self):
        """Custom components in calendar survive round-trip."""
        original = b"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//EN
BEGIN:X-MYAPP
X-SETTING:value
END:X-MYAPP
END:VCALENDAR
"""
        cal = Calendar.from_ical(original)
        regenerated = cal.to_ical()
        assert b"BEGIN:X-MYAPP" in regenerated
        assert b"X-SETTING:value" in regenerated


class TestCustomComponentAPI:
    """Test that custom components work with standard Component API."""

    def test_add_property_to_custom_component(self):
        """Can add properties to custom component."""
        comp = Component(name="X-TEST")
        comp.add("summary", "Test Summary")
        comp.add("x-custom", "Custom Value")
        assert comp["SUMMARY"] == "Test Summary"
        assert comp["X-CUSTOM"] == "Custom Value"

    def test_add_subcomponent_to_custom_component(self):
        """Can add subcomponents to custom component."""
        container = Component(name="X-CONTAINER")
        event = Event()
        event.add("uid", "123")
        event.add("summary", "Test Event")

        container.add_component(event)
        assert len(container.subcomponents) == 1
        assert container.subcomponents[0].name == "VEVENT"

    def test_custom_component_iteration(self):
        """Can iterate over properties in custom component."""
        comp = Component(name="X-TEST")
        comp.add("prop1", "value1")
        comp.add("prop2", "value2")

        # property_items() includes BEGIN, END, and all component properties
        props = list(comp.property_items())
        prop_names = [name for name, value in props]
        assert "PROP1" in prop_names
        assert "PROP2" in prop_names
        assert "BEGIN" in prop_names
        assert "END" in prop_names

    def test_custom_component_get_method(self):
        """Can use get() method on custom component."""
        comp = Component(name="X-TEST")
        comp.add("existing", "value")

        assert comp.get("EXISTING") == "value"
        assert comp.get("NONEXISTENT") is None
        assert comp.get("NONEXISTENT", "default") == "default"


class TestRFC5545Compliance:
    """Test RFC 5545 compliance for custom components."""

    def test_preserves_x_components(self):
        """X-components (vendor-specific) are preserved."""
        ics_data = b"""BEGIN:VCALENDAR
VERSION:2.0
BEGIN:X-VENDOR-COMP
X-VENDOR-PROP:proprietary
END:X-VENDOR-COMP
END:VCALENDAR
"""
        cal = Calendar.from_ical(ics_data)
        regenerated = cal.to_ical()

        # X-component preserved
        assert b"X-VENDOR-COMP" in regenerated
        assert b"X-VENDOR-PROP" in regenerated

    def test_preserves_iana_components(self):
        """IANA-registered components are preserved."""
        # Hypothetical IANA component (not X- prefixed)
        ics_data = b"""BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VFUTURE
UID:future-1
SUMMARY:Future IANA component
END:VFUTURE
END:VCALENDAR
"""
        cal = Calendar.from_ical(ics_data)
        regenerated = cal.to_ical()

        # IANA component preserved
        assert b"VFUTURE" in regenerated
        assert b"Future IANA component" in regenerated

    def test_does_not_silently_drop_custom_components(self):
        """Custom components are never silently dropped (RFC 5545)."""
        ics_data = b"""BEGIN:VCALENDAR
VERSION:2.0
BEGIN:X-UNKNOWN1
UID:1
END:X-UNKNOWN1
BEGIN:X-UNKNOWN2
UID:2
END:X-UNKNOWN2
BEGIN:UNKNOWN3
UID:3
END:UNKNOWN3
END:VCALENDAR
"""
        cal = Calendar.from_ical(ics_data)

        # All 3 custom components preserved
        assert len(cal.subcomponents) == 3
        component_names = {comp.name for comp in cal.subcomponents}
        assert component_names == {"X-UNKNOWN1", "X-UNKNOWN2", "UNKNOWN3"}

    def test_nested_custom_components_preserved(self):
        """Nested custom components are fully preserved."""
        ics_data = b"""BEGIN:X-OUTER
SUMMARY:Outer
BEGIN:X-INNER
SUMMARY:Inner
END:X-INNER
END:X-OUTER
"""
        outer = Component.from_ical(ics_data)
        assert outer.name == "X-OUTER"
        assert len(outer.subcomponents) == 1

        inner = outer.subcomponents[0]
        assert inner.name == "X-INNER"
        assert inner["SUMMARY"] == "Inner"

        # Round-trip preserves nesting
        regenerated = outer.to_ical()
        reparsed = Component.from_ical(regenerated)
        assert len(reparsed.subcomponents) == 1
        assert reparsed.subcomponents[0].name == "X-INNER"

"""Tests for Component.register() method."""

import pytest

from icalendar import Component


class TestComponentRegister:
    """Test Component.register() method."""

    def test_register_custom_component(self):
        """Register a custom component and use it."""

        class XMyComponent(Component):
            name = "X-MY-COMPONENT"

            def custom_method(self):
                return "custom_value"

        Component.register(XMyComponent)

        # Get the registered component
        retrieved = Component.get_component_class("X-MY-COMPONENT")
        assert retrieved is XMyComponent

        # Create instance
        comp = retrieved()
        assert comp.name == "X-MY-COMPONENT"
        assert comp.custom_method() == "custom_value"

    def test_register_component_without_name_raises(self):
        """Registering component without name attribute raises ValueError."""

        class BadComponent(Component):
            pass  # No name attribute

        with pytest.raises(ValueError, match="must have a 'name' attribute"):
            Component.register(BadComponent)

    def test_register_component_with_none_name_raises(self):
        """Registering component with None name raises ValueError."""

        class BadComponent(Component):
            name = None

        with pytest.raises(ValueError, match="must have a 'name' attribute"):
            Component.register(BadComponent)

    def test_register_duplicate_component_raises(self):
        """Registering same component name twice raises ValueError."""

        class XComponent1(Component):
            name = "X-DUPLICATE"

        class XComponent2(Component):
            name = "X-DUPLICATE"

        Component.register(XComponent1)

        with pytest.raises(ValueError, match="already registered"):
            Component.register(XComponent2)

    def test_register_same_class_twice_allowed(self):
        """Registering the exact same class twice is allowed (idempotent)."""

        class XComponent(Component):
            name = "X-IDEMPOTENT"

        Component.register(XComponent)
        Component.register(XComponent)  # Should not raise

    def test_parse_uses_registered_component(self):
        """Parsing uses the registered custom component class."""

        class XVendor(Component):
            name = "X-VENDOR"

            def get_vendor_id(self):
                return self.get("X-VENDOR-ID")

        Component.register(XVendor)

        ical_data = b"""BEGIN:X-VENDOR
UID:123
X-VENDOR-ID:vendor-1
END:X-VENDOR
"""
        comp = Component.from_ical(ical_data)

        assert isinstance(comp, XVendor)
        assert comp.name == "X-VENDOR"
        assert str(comp.get_vendor_id()) == "vendor-1"

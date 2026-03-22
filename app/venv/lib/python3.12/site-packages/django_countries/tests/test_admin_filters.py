import inspect

import pytest
from django.contrib import admin
from django.contrib.admin.views.main import ChangeList
from django.contrib.auth.models import AnonymousUser
from django.test import TestCase
from django.test.client import RequestFactory

from django_countries import countries, filters
from django_countries.tests import models

test_site = admin.AdminSite(name="test-admin")


class PersonAdmin(admin.ModelAdmin):
    list_filter = [("country", filters.CountryFilter)]


test_site.register(models.Person, PersonAdmin)


class MultiCountryAdmin(admin.ModelAdmin):
    list_filter = [("countries", filters.CountryFilter)]


test_site.register(models.MultiCountry, MultiCountryAdmin)


class PaymentAdmin(admin.ModelAdmin):
    """Admin for Payment model that filters through contact__country relation."""

    list_filter = [("contact__country", filters.CountryFilter)]


test_site.register(models.Payment, PaymentAdmin)


class TestCountryFilter(TestCase):
    def get_changelist_kwargs(self):
        m = self.person_admin
        sig = inspect.signature(ChangeList.__init__)
        kwargs = {"model_admin": m}
        for arg in list(sig.parameters)[2:]:
            if hasattr(m, arg):
                kwargs[arg] = getattr(m, arg)
        return kwargs

    def setUp(self):
        models.Person.objects.create(name="Alice", country="NZ")
        models.Person.objects.create(name="Bob", country="AU")
        models.Person.objects.create(name="Chris", country="NZ")
        self.person_admin = PersonAdmin(models.Person, test_site)

    def test_filter_none(self):
        request = RequestFactory().get("/person/")
        request.user = AnonymousUser()
        cl = ChangeList(request, **self.get_changelist_kwargs())
        cl.get_results(request)
        self.assertEqual(list(cl.result_list), list(models.Person.objects.all()))

    def test_filter_country(self):
        request = RequestFactory().get("/person/", data={"country": "NZ"})
        request.user = AnonymousUser()
        cl = ChangeList(request, **self.get_changelist_kwargs())
        cl.get_results(request)
        self.assertEqual(
            list(cl.result_list), list(models.Person.objects.exclude(country="AU"))
        )

    def _test_choices(self, selected_country_code="NZ"):
        request_params = {}
        selected_country = "All"

        if selected_country_code:
            request_params["country"] = selected_country_code
            selected_country = countries.name(selected_country_code)

        request = RequestFactory().get("/person/", data=request_params)
        request.user = AnonymousUser()
        cl = ChangeList(request, **self.get_changelist_kwargs())
        choices = list(cl.filter_specs[0].choices(cl))
        self.assertEqual(
            [c["display"] for c in choices], ["All", "Australia", "New Zealand"]
        )
        for choice in choices:
            self.assertEqual(choice["selected"], choice["display"] == selected_country)

    def test_choices(self):
        return self._test_choices()

    def test_choices_empty_selection(self):
        return self._test_choices(selected_country_code=None)


class PersonAutocompleteAdmin(admin.ModelAdmin):
    """Admin class attempting to use autocomplete_fields."""

    autocomplete_fields = ["country"]


test_site.register(models.AllowNull, PersonAutocompleteAdmin)


class TestAutocompleteFields(TestCase):
    """Test to document that CountryField does not support autocomplete_fields.

    This test documents the current behavior where autocomplete_fields
    does not work as expected with CountryField. The field doesn't raise
    an error, but it doesn't provide autocomplete functionality either.

    See: https://github.com/SmileyChris/django-countries/issues/473
    """

    def setUp(self):
        self.admin = PersonAutocompleteAdmin(models.AllowNull, test_site)

    def test_autocomplete_fields_in_admin_config(self):
        """Verify autocomplete_fields can be set but doesn't work."""
        # The field can be added to autocomplete_fields without error
        self.assertEqual(self.admin.autocomplete_fields, ["country"])

        # However, CountryField doesn't implement the autocomplete widget/view
        # It will fall back to a regular select widget
        # (This test documents current behavior, not desired behavior)


class TestDjangoFiltersIntegration(TestCase):
    """Tests for django_countries.django_filters.CountryFilter."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.django_filters = pytest.importorskip("django_filters")
        from django_countries.django_filters import CountryFilter

        cls.country_filter = CountryFilter

    def setUp(self):
        models.Person.objects.create(name="Alice", country="NZ")
        models.Person.objects.create(name="Bob", country="AU")
        models.Person.objects.create(name="Charlie", country="US")

    def test_django_filters_country_filter_basic(self):
        """Test basic usage of the integration CountryFilter."""

        filter_class = self.country_filter

        class PersonFilterSet(self.django_filters.FilterSet):
            country = filter_class()

            class Meta:
                model = models.Person
                fields = ["country"]

        # Test filtering by country
        filterset = PersonFilterSet(
            data={"country": "NZ"}, queryset=models.Person.objects.all()
        )
        self.assertTrue(filterset.is_valid())
        results = list(filterset.qs)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "Alice")

    def test_django_filters_country_filter_with_empty_label(self):
        """Test integration CountryFilter with custom empty_label."""

        filter_class = self.country_filter

        class PersonFilterSet(self.django_filters.FilterSet):
            country = filter_class(empty_label="Any Country")

            class Meta:
                model = models.Person
                fields = ["country"]

        filterset = PersonFilterSet(queryset=models.Person.objects.all())
        # Check that the filter was created successfully
        self.assertIn("country", filterset.filters)
        # Check that empty_label was set on the field
        self.assertEqual(filterset.filters["country"].field.empty_label, "Any Country")

    def test_django_filters_country_filter_has_choices(self):
        """Test that integration CountryFilter has country choices."""

        filter_class = self.country_filter

        class PersonFilterSet(self.django_filters.FilterSet):
            country = filter_class()

            class Meta:
                model = models.Person
                fields = ["country"]

        filterset = PersonFilterSet(queryset=models.Person.objects.all())
        choices = list(filterset.filters["country"].field.choices)
        # Should have many country choices
        self.assertGreater(len(choices), 200)
        # Check specific countries are in choices
        country_codes = [code for code, name in choices]
        self.assertIn("NZ", country_codes)
        self.assertIn("AU", country_codes)
        self.assertIn("US", country_codes)

    def test_django_filters_country_filter_no_filter_returns_all(self):
        """Test that not applying filter returns all results."""

        filter_class = self.country_filter

        class PersonFilterSet(self.django_filters.FilterSet):
            country = filter_class()

            class Meta:
                model = models.Person
                fields = ["country"]

        filterset = PersonFilterSet(data={}, queryset=models.Person.objects.all())
        self.assertEqual(filterset.qs.count(), 3)


class TestMultiCountryFilter(TestCase):
    """Tests for CountryFilter with multiple=True fields."""

    def get_changelist_kwargs(self):
        m = self.multi_country_admin
        sig = inspect.signature(ChangeList.__init__)
        kwargs = {"model_admin": m}
        for arg in list(sig.parameters)[2:]:
            if hasattr(m, arg):
                kwargs[arg] = getattr(m, arg)
        return kwargs

    def setUp(self):
        models.MultiCountry.objects.create(countries=["NZ"])
        models.MultiCountry.objects.create(countries=["FR", "AU"])
        models.MultiCountry.objects.create(countries=["FR", "NZ"])
        self.multi_country_admin = MultiCountryAdmin(models.MultiCountry, test_site)

    def test_filter_none(self):
        """Test that no filter returns all records."""
        request = RequestFactory().get("/multi_country/")
        request.user = AnonymousUser()
        cl = ChangeList(request, **self.get_changelist_kwargs())
        cl.get_results(request)
        self.assertEqual(len(cl.result_list), models.MultiCountry.objects.count())

    def test_filter_country(self):
        """Test filtering by a single country using __contains lookup."""
        request = RequestFactory().get(
            "/multi_country/", data={"countries__contains": "NZ"}
        )
        request.user = AnonymousUser()
        cl = ChangeList(request, **self.get_changelist_kwargs())
        cl.get_results(request)
        # Should return records containing NZ (excluding the one with only FR,AU)
        expected = models.MultiCountry.objects.filter(countries__contains="NZ")
        self.assertCountEqual(
            list(cl.result_list),
            list(expected),
        )

    def test_filter_different_country(self):
        """Test filtering by a different country."""
        request = RequestFactory().get(
            "/multi_country/", data={"countries__contains": "FR"}
        )
        request.user = AnonymousUser()
        cl = ChangeList(request, **self.get_changelist_kwargs())
        cl.get_results(request)
        expected = models.MultiCountry.objects.filter(countries__contains="FR")
        self.assertCountEqual(
            list(cl.result_list),
            list(expected),
        )

    def _test_choices(self, selected_country_code="NZ"):
        """Helper to test filter choices display correctly."""
        request_params = {}
        selected_country = "All"

        if selected_country_code:
            request_params["countries__contains"] = selected_country_code
            selected_country = countries.name(selected_country_code)

        request = RequestFactory().get("/multi_country/", data=request_params)
        request.user = AnonymousUser()
        cl = ChangeList(request, **self.get_changelist_kwargs())
        choices = list(cl.filter_specs[0].choices(cl))
        # Should show all countries that appear in the data
        self.assertEqual(
            [c["display"] for c in choices],
            ["All", "Australia", "France", "New Zealand"],
        )
        for choice in choices:
            self.assertEqual(choice["selected"], choice["display"] == selected_country)

    def test_choices(self):
        """Test filter choices with a selected country."""
        return self._test_choices()

    def test_choices_empty_selection(self):
        """Test filter choices with no country selected."""
        return self._test_choices(selected_country_code=None)


class TestRelatedCountryFilter(TestCase):
    """Tests for CountryFilter on related fields (issue #432)."""

    def get_changelist_kwargs(self):
        m = self.payment_admin
        sig = inspect.signature(ChangeList.__init__)
        kwargs = {"model_admin": m}
        for arg in list(sig.parameters)[2:]:
            if hasattr(m, arg):
                kwargs[arg] = getattr(m, arg)
        return kwargs

    def setUp(self):
        # Create contacts with countries
        contact_nz = models.Contact.objects.create(name="Alice", country="NZ")
        contact_au = models.Contact.objects.create(name="Bob", country="AU")
        contact_us = models.Contact.objects.create(name="Charlie", country="US")

        # Create payments linked to contacts
        models.Payment.objects.create(contact=contact_nz, amount=100)
        models.Payment.objects.create(contact=contact_au, amount=200)
        models.Payment.objects.create(contact=contact_nz, amount=150)
        models.Payment.objects.create(contact=contact_us, amount=300)

        self.payment_admin = PaymentAdmin(models.Payment, test_site)

    def test_filter_none(self):
        """Test that no filter returns all payments."""
        request = RequestFactory().get("/payment/")
        request.user = AnonymousUser()
        cl = ChangeList(request, **self.get_changelist_kwargs())
        cl.get_results(request)
        self.assertEqual(list(cl.result_list), list(models.Payment.objects.all()))

    def test_filter_related_country(self):
        """Test filtering payments by contact__country."""
        request = RequestFactory().get("/payment/", data={"contact__country": "NZ"})
        request.user = AnonymousUser()
        cl = ChangeList(request, **self.get_changelist_kwargs())
        cl.get_results(request)
        # Should return only payments from New Zealand contacts
        expected = models.Payment.objects.filter(contact__country="NZ")
        self.assertEqual(list(cl.result_list), list(expected))

    def test_expected_parameters(self):
        """Test that expected_parameters returns the correct field path."""
        request = RequestFactory().get("/payment/")
        request.user = AnonymousUser()
        cl = ChangeList(request, **self.get_changelist_kwargs())
        filter_spec = cl.filter_specs[0]

        # Should expect 'contact__country' not just 'country'
        expected = filter_spec.expected_parameters()
        self.assertEqual(expected, ["contact__country"])

    def test_choices_related_field(self):
        """Test that filter choices work for related country fields."""
        request = RequestFactory().get("/payment/", data={"contact__country": "AU"})
        request.user = AnonymousUser()
        cl = ChangeList(request, **self.get_changelist_kwargs())
        choices = list(cl.filter_specs[0].choices(cl))

        # Should show all countries that appear in the related contacts
        self.assertEqual(
            [c["display"] for c in choices],
            ["All", "Australia", "New Zealand", "United States of America"],
        )

        # Australia should be selected
        for choice in choices:
            if choice["display"] == "Australia":
                self.assertTrue(choice["selected"])
            else:
                self.assertFalse(choice["selected"])

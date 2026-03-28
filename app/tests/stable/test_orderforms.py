from decimal import Decimal

import pytest

from eventyay.base.models import Product
from eventyay.base.services.system_questions import (
    get_system_question_asked_required,
    get_system_question_state,
    set_system_question_field_overrides,
)


@pytest.mark.django_db
class TestOrderFormDefaultFields:
    @pytest.fixture(autouse=True)
    def _set_site_url(self, settings):
        settings.SITE_URL = 'https://testserver'

    def test_global_default_field_state_without_overrides(self, event):
        product = Product.objects.create(
            event=event,
            name='In-person Ticket',
            default_price=Decimal('10.00'),
            admission=True,
            position=1,
        )
        event.settings.attendee_names_asked = True
        event.settings.attendee_names_required = False

        assert get_system_question_state(event, 'attendee_name_parts', product) == 'optional'
        assert get_system_question_asked_required(event, 'attendee_name_parts', product) == (True, False)

    def test_product_override_takes_precedence(self, event):
        in_person = Product.objects.create(
            event=event,
            name='In-person Ticket',
            default_price=Decimal('20.00'),
            admission=True,
            position=1,
        )
        virtual = Product.objects.create(
            event=event,
            name='Virtual Ticket',
            default_price=Decimal('5.00'),
            admission=True,
            position=2,
        )

        event.settings.attendee_names_asked = False
        event.settings.attendee_names_required = False
        set_system_question_field_overrides(event, 'attendee_name_parts', {str(in_person.pk): 'required'})

        assert get_system_question_asked_required(event, 'attendee_name_parts', in_person) == (True, True)
        assert get_system_question_asked_required(event, 'attendee_name_parts', virtual) == (False, False)

    def test_default_field_settings_page_saves_overrides_and_name_settings(self, organizer_client, organizer, event):
        in_person = Product.objects.create(
            event=event,
            name='In-person Ticket',
            default_price=Decimal('20.00'),
            admission=True,
            position=1,
        )
        virtual = Product.objects.create(
            event=event,
            name='Virtual Ticket',
            default_price=Decimal('5.00'),
            admission=True,
            position=2,
        )

        response = organizer_client.post(
            f'/control/event/{organizer.slug}/{event.slug}/orderforms/default-fields/attendee_name_parts/',
            {
                'global_state': 'do_not_ask',
                f'product_{in_person.pk}': 'required',
                f'product_{virtual.pk}': 'default',
                'name_scheme': 'given_family',
                'name_scheme_titles': 'english_common',
            },
            follow=True,
        )

        assert response.status_code == 200

        event.settings.flush()
        assert event.settings.attendee_names_asked is False
        assert event.settings.attendee_names_required is False
        assert event.settings.name_scheme == 'given_family'
        assert event.settings.name_scheme_titles == 'english_common'

        overrides = event.settings.get('system_question_product_overrides', as_type=dict)
        assert overrides['attendee_name_parts'][str(in_person.pk)] == 'required'
        assert str(virtual.pk) not in overrides['attendee_name_parts']

    def test_orderforms_page_links_to_default_field_settings(self, organizer_client, organizer, event):
        Product.objects.create(
            event=event,
            name='In-person Ticket',
            default_price=Decimal('20.00'),
            admission=True,
            position=1,
        )
        event.settings.attendee_names_asked = True
        event.settings.attendee_names_required = False

        response = organizer_client.get(
            f'/control/event/{organizer.slug}/{event.slug}/orderforms/',
            follow=True,
        )

        assert response.status_code == 200
        content = response.content.decode()
        assert (
            f'/control/event/{organizer.slug}/{event.slug}/orderforms/default-fields/attendee_name_parts/'
            in content
        )
        assert 'Name format' not in content

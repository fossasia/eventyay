import datetime

from django.test import override_settings
from django_scopes import scopes_disabled

from eventyay.base.models import Event, Organizer, Team, User
from eventyay.control.forms.event import QuickSetupForm
from tests.tickets.base import SoupTest


@override_settings(SITE_URL='https://testserver')
class QuickstartSearchableCurrencyTest(SoupTest):
    @scopes_disabled()
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user('dummy@dummy.dummy', 'dummy')
        self.orga1 = Organizer.objects.create(name='CCC', slug='ccc')
        self.event1 = Event.objects.create(
            organizer=self.orga1,
            name='30C3',
            slug='30c3',
            date_from=datetime.datetime(2026, 12, 26, tzinfo=datetime.UTC),
        )

        t = Team.objects.create(
            organizer=self.orga1,
            can_create_events=True,
            can_change_event_settings=True,
            can_change_items=True,
        )
        t.members.add(self.user)
        t.limit_events.add(self.event1)

        self.client.login(email='dummy@dummy.dummy', password='dummy')

    @scopes_disabled()
    def test_quicksetup_form_currency_has_searchable_select_attrs(self):
        form = QuickSetupForm(event=self.event1)
        attrs = form.fields['currency'].widget.attrs
        assert 'data-searchable-select' in attrs
        assert attrs.get('data-search-placeholder') == 'Search'
        assert attrs.get('data-empty-text') == 'No results'

    @scopes_disabled()
    def test_quickstart_template_includes_searchable_select_assets_and_markup(self):
        doc = self.get_doc(f'/control/event/{self.orga1.slug}/{self.event1.slug}/quickstart/')
        assert any('searchable-select.css' in link.get('href', '') for link in doc.select('link[rel=stylesheet]'))
        assert any('searchable-select.js' in s.get('src', '') for s in doc.select('script'))

        currency_select = doc.select('#id_currency')
        assert currency_select, 'id_currency select element not found'
        assert 'data-searchable-select' in currency_select[0].attrs

import datetime
from unittest.mock import patch

import pytest
from django.db import transaction
from django.test import override_settings
from django.urls import reverse
from django_scopes import scopes_disabled

from eventyay.base.models import Event, Organizer, Team, User
from tests.tickets.base import SoupTest, extract_form_fields


@pytest.fixture
def class_monkeypatch(request, monkeypatch):
    request.cls.monkeypatch = monkeypatch


@override_settings(SITE_URL='https://testserver')
@pytest.mark.usefixtures('class_monkeypatch')
class OrganizerTest(SoupTest):
    @scopes_disabled()
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user('dummy@dummy.dummy', 'dummy')
        self.orga1 = Organizer.objects.create(name='CCC', slug='ccc')
        self.orga2 = Organizer.objects.create(name='MRM', slug='mrm')
        self.event1 = Event.objects.create(
            organizer=self.orga1,
            name='30C3',
            slug='30c3',
            date_from=datetime.datetime(2013, 12, 26, tzinfo=datetime.UTC),
            plugins='eventyay.plugins.banktransfer,tests.tickets.testdummy',
        )

        t = Team.objects.create(
            organizer=self.orga1,
            can_create_events=True,
            can_change_event_settings=True,
            can_change_items=True,
            can_change_organizer_settings=True,
        )
        t.members.add(self.user)
        t.limit_events.add(self.event1)

        self.client.login(email='dummy@dummy.dummy', password='dummy')

    def test_organizer_list(self):
        doc = self.get_doc('/control/organizers/')
        tabletext = doc.select('#page-wrapper .table')[0].text
        self.assertIn('CCC', tabletext)
        self.assertNotIn('MRM', tabletext)

    def test_organizer_list_empty_state(self):
        doc = self.get_doc('/control/organizers/?query=nonexistentorg123')
        tabletext = doc.select('#page-wrapper .table')[0].text
        self.assertIn('No organizers found.', tabletext)

    def test_organizer_detail(self):
        doc = self.get_doc('/control/organizer/ccc/')
        tabletext = doc.select('#page-wrapper .table')[0].text
        self.assertIn('30C3', tabletext)

    def test_organizer_detail_empty_state(self):
        doc = self.get_doc('/control/organizer/ccc/?query=nonexistentevent123')
        tabletext = doc.select('#page-wrapper .table')[0].text
        self.assertIn('No events found.', tabletext)

    def test_organizer_detail_shows_clone_link_when_user_can_clone(self):
        clone_url = reverse(
            'eventyay_common:event.clone',
            kwargs={'organizer': self.orga1.slug, 'event': self.event1.slug},
        )
        doc = self.get_doc('/control/organizer/ccc/')
        self.assertIn(clone_url, doc.decode())

    def test_organizer_detail_hides_clone_link_without_event_settings_permission(self):
        with scopes_disabled():
            limited_team = Team.objects.create(
                organizer=self.orga1,
                can_create_events=True,
                can_change_event_settings=False,
                can_change_items=True,
            )
            limited_user = User.objects.create_user('limited@dummy.dummy', 'dummy')
            limited_team.members.add(limited_user)
            limited_team.limit_events.add(self.event1)

        self.client.login(email='limited@dummy.dummy', password='dummy')
        clone_url = reverse(
            'eventyay_common:event.clone',
            kwargs={'organizer': self.orga1.slug, 'event': self.event1.slug},
        )
        doc = self.get_doc('/control/organizer/ccc/')
        self.assertNotIn(clone_url, doc.decode())

    def test_organizer_detail_hides_clone_link_without_create_events_permission(self):
        with scopes_disabled():
            nocreate_team = Team.objects.create(
                organizer=self.orga1,
                can_create_events=False,
                can_change_event_settings=True,
                can_change_items=True,
            )
            nocreate_user = User.objects.create_user('nocreate@dummy.dummy', 'dummy')
            nocreate_team.members.add(nocreate_user)
            nocreate_team.limit_events.add(self.event1)

        self.client.login(email='nocreate@dummy.dummy', password='dummy')
        clone_url = reverse(
            'eventyay_common:event.clone',
            kwargs={'organizer': self.orga1.slug, 'event': self.event1.slug},
        )
        doc = self.get_doc('/control/organizer/ccc/')
        self.assertNotIn(clone_url, doc.decode())

    def test_organizer_detail_shows_clone_link_for_staff_session(self):
        with scopes_disabled():
            User.objects.create_user('staff@dummy.dummy', 'dummy', is_staff=True)

        self.client.login(email='staff@dummy.dummy', password='dummy')
        clone_url = reverse(
            'eventyay_common:event.clone',
            kwargs={'organizer': self.orga1.slug, 'event': self.event1.slug},
        )
        with patch.object(User, 'has_active_staff_session', return_value=True):
            doc = self.get_doc('/control/organizer/ccc/')
        self.assertIn(clone_url, doc.decode())

    def test_organizer_settings(self):
        url = reverse('eventyay_common:organizer.edit', kwargs={'organizer': self.orga1.slug})
        doc = self.get_doc(url)
        doc.select('[name=name]')[0]['value'] = 'CCC e.V.'

        doc = self.post_doc(
            url,
            extract_form_fields(doc.select('.container-fluid form')[0]),
        )
        assert len(doc.select('.alert-success')) > 0
        assert doc.select('[name=name]')[0]['value'] == 'CCC e.V.'
        self.orga1.refresh_from_db()
        assert self.orga1.name == 'CCC e.V.'

    def test_organizer_display_settings(self):
        called = False

        def set_called(*args, **kwargs):
            nonlocal called
            called = True

        url = reverse('eventyay_common:organizer.edit', kwargs={'organizer': self.orga1.slug})
        self.monkeypatch.setattr('eventyay.presale.style.regenerate_organizer_css.apply_async', set_called)
        assert not self.orga1.settings.presale_css_checksum
        doc = self.get_doc(url)
        doc.select('[name=settings-primary_color]')[0]['value'] = '#33c33c'

        with transaction.atomic():
            doc = self.post_doc(
                url,
                extract_form_fields(doc.select('.container-fluid form')[0]),
            )
            assert len(doc.select('.alert-success')) > 0
            assert doc.select('[name=settings-primary_color]')[0]['value'] == '#33c33c'
        self.orga1.settings.flush()
        assert self.orga1.settings.primary_color == '#33c33c'
        assert called

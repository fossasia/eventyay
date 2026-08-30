from unittest.mock import patch

import pytest
from django.test import RequestFactory, TestCase
from django.urls import resolve, reverse

from eventyay.base.models import User
from eventyay.control.navigation import get_admin_navigation


def _make_admin(email='admin@example.com', password='admin_pw_123!'):
    admin = User.objects.create_user(email, password)
    admin.is_staff = True
    admin.is_superuser = True
    admin.save()
    return admin


def _find_nav_item(nav, label):
    for item in nav:
        if str(item.get('label')) == label:
            return item
    return None


@pytest.mark.django_db
class TestAdminNavigationUnit:
    def test_platform_data_menu_structure(self, rf: RequestFactory):
        user = _make_admin()
        request = rf.get(reverse('eventyay_admin:admin.dashboard'))
        request.user = user
        request.resolver_match = resolve(reverse('eventyay_admin:admin.dashboard'))

        nav = get_admin_navigation(request)

        # Ensure old standalone items are removed
        assert _find_nav_item(nav, 'All Events') is None
        assert _find_nav_item(nav, 'All Organizers') is None
        assert _find_nav_item(nav, 'All Attendees') is None
        assert _find_nav_item(nav, 'All Sessions') is None
        assert _find_nav_item(nav, 'All Orders') is None

        # Ensure Platform Data parent exists
        platform_data = _find_nav_item(nav, 'Platform Data')
        assert platform_data is not None
        assert platform_data['icon'] == 'database'
        assert platform_data['url'] == reverse('eventyay_admin:admin.events')
        assert platform_data['active'] is False
        assert 'children' in platform_data

        # Verify exactly the five expected submenu labels in exact order
        children = platform_data['children']
        child_labels = [str(child['label']) for child in children]
        assert child_labels == ['Events', 'Organizers', 'Attendees', 'Sessions', 'Orders']

        # Verify URLs for all submenu items
        assert children[0]['url'] == reverse('eventyay_admin:admin.events')
        assert children[1]['url'] == reverse('eventyay_admin:admin.organizers')
        assert children[2]['url'] == reverse('eventyay_admin:admin.attendees')
        assert children[3]['url'] == reverse('eventyay_admin:admin.submissions')
        assert children[4]['url'] == reverse('eventyay_admin:admin.orders')

        # When on dashboard, none of the Platform Data children are active
        for child in children:
            assert child['active'] is False

    @pytest.mark.parametrize(
        'route_name,active_index,active_label',
        [
            ('eventyay_admin:admin.events', 0, 'Events'),
            ('eventyay_admin:admin.organizers', 1, 'Organizers'),
            ('eventyay_admin:admin.attendees', 2, 'Attendees'),
            ('eventyay_admin:admin.submissions', 3, 'Sessions'),
            ('eventyay_admin:admin.orders', 4, 'Orders'),
        ],
    )
    def test_platform_data_active_child_state(self, rf: RequestFactory, route_name, active_index, active_label):
        user = _make_admin()
        url = reverse(route_name)
        request = rf.get(url)
        request.user = user
        request.resolver_match = resolve(url)

        nav = get_admin_navigation(request)
        platform_data = _find_nav_item(nav, 'Platform Data')
        assert platform_data is not None

        children = platform_data['children']
        for i, child in enumerate(children):
            if i == active_index:
                assert child['active'] is True, f'Expected {active_label} (index {i}) to be active'
            else:
                assert child['active'] is False, f'Expected {child["label"]} (index {i}) to be inactive'


class TestAdminSidebarRendering(TestCase):
    def setUp(self):
        self.admin = _make_admin()
        self.client.force_login(self.admin)
        session = self.client.session
        session['pretix_auth_login_time'] = 1234567890
        session['pretix_auth_long_session'] = False
        session.save()

    @patch.object(User, 'has_active_staff_session', return_value=True)
    def test_sidebar_renders_platform_data_and_submenus(self, mock_staff):
        response = self.client.get(reverse('eventyay_admin:admin.dashboard'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()

        # Check Platform Data header and child labels
        self.assertIn('Platform Data', content)
        self.assertIn('Events', content)
        self.assertIn('Organizers', content)
        self.assertIn('Attendees', content)
        self.assertIn('Sessions', content)
        self.assertIn('Orders', content)

        # Check old labels are not present in rendered sidebar
        self.assertNotIn('All Events', content)
        self.assertNotIn('All Organizers', content)
        self.assertNotIn('All Attendees', content)
        self.assertNotIn('All Sessions', content)
        self.assertNotIn('All Orders', content)

    @patch.object(User, 'has_active_staff_session', return_value=True)
    def test_sidebar_child_active_classes(self, mock_staff):
        routes_to_labels = [
            (reverse('eventyay_admin:admin.events'), 'Events'),
            (reverse('eventyay_admin:admin.organizers'), 'Organizers'),
            (reverse('eventyay_admin:admin.attendees'), 'Attendees'),
            (reverse('eventyay_admin:admin.submissions'), 'Sessions'),
            (reverse('eventyay_admin:admin.orders'), 'Orders'),
        ]

        for url, label in routes_to_labels:
            with self.subTest(url=url, label=label):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                content = response.content.decode()

                # Ensure active class is on the active child item
                self.assertRegex(content, rf'<a href="{url}"\s+class="active">')
                # Ensure other child items do not have class="active"
                for other_url, _ in routes_to_labels:
                    if other_url != url:
                        self.assertNotRegex(content, rf'<a href="{other_url}"\s+class="active">')
                self.assertIn('has-children', content)
                self.assertIn('nav-second-level', content)

    @patch.object(User, 'has_active_staff_session', return_value=True)
    def test_navigation_between_child_pages_updates_active_state(self, mock_staff):
        # 1. Visit Events
        resp = self.client.get(reverse('eventyay_admin:admin.events'))
        self.assertRegex(
            resp.content.decode(), rf'<a href="{reverse("eventyay_admin:admin.events")}"\s+class="active">'
        )

        # 2. Navigate to Organizers
        resp = self.client.get(reverse('eventyay_admin:admin.organizers'))
        self.assertRegex(
            resp.content.decode(), rf'<a href="{reverse("eventyay_admin:admin.organizers")}"\s+class="active">'
        )
        self.assertNotRegex(
            resp.content.decode(), rf'<a href="{reverse("eventyay_admin:admin.events")}"\s+class="active">'
        )

        # 3. Navigate to Attendees
        resp = self.client.get(reverse('eventyay_admin:admin.attendees'))
        self.assertRegex(
            resp.content.decode(), rf'<a href="{reverse("eventyay_admin:admin.attendees")}"\s+class="active">'
        )
        self.assertNotRegex(
            resp.content.decode(), rf'<a href="{reverse("eventyay_admin:admin.organizers")}"\s+class="active">'
        )

        # 4. Navigate to Sessions
        resp = self.client.get(reverse('eventyay_admin:admin.submissions'))
        self.assertRegex(
            resp.content.decode(), rf'<a href="{reverse("eventyay_admin:admin.submissions")}"\s+class="active">'
        )

        # 5. Navigate to Orders
        resp = self.client.get(reverse('eventyay_admin:admin.orders'))
        self.assertRegex(
            resp.content.decode(), rf'<a href="{reverse("eventyay_admin:admin.orders")}"\s+class="active">'
        )

        # 6. Refresh Orders page
        resp_refresh = self.client.get(reverse('eventyay_admin:admin.orders'))
        self.assertRegex(
            resp_refresh.content.decode(), rf'<a href="{reverse("eventyay_admin:admin.orders")}"\s+class="active">'
        )
        self.assertIn('Platform Data', resp_refresh.content.decode())

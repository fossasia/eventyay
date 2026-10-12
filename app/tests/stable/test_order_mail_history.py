from datetime import timedelta
from decimal import Decimal

import pytest
from django.test import override_settings
from django.utils import timezone
from django_scopes import scope

from eventyay.base.models import Order


@pytest.fixture
def order(event):
    """A paid order with an email address."""
    with scope(organizer=event.organizer):
        return Order.objects.create(
            event=event,
            code='MAILHIST',
            email='buyer@example.org',
            status=Order.STATUS_PAID,
            datetime=timezone.now(),
            expires=timezone.now() + timedelta(days=1),
            total=Decimal('10.00'),
            locale='en',
        )


def order_url(order):
    """Return the organizer URL of the order's detail page."""
    return f'/control/event/{order.event.organizer.slug}/{order.event.slug}/orders/{order.code}/'


def log_email(order, action_type, message):
    """Log an email for the order the way send_mail does."""
    with scope(organizer=order.event.organizer):
        order.log_action(
            action_type,
            data={'subject': 'Your order', 'message': message, 'recipient': order.email},
        )


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_custom_email_is_shown_as_formatted_text(organizer_client, order):
    """A custom email from the rich text editor is shown as paragraphs, not as HTML tags."""
    organizer_client.post(
        order_url(order) + 'sendmail',
        {
            'sendto': order.email,
            'subject': 'Keynote seat',
            'message': '<p>Hello Aisha,</p><p>Your seat is reserved.</p>',
        },
    )

    content = organizer_client.get(order_url(order) + 'mail_history').content.decode()

    assert 'Keynote seat' in content
    assert '<p>Hello Aisha,</p><p>Your seat is reserved.</p>' in content
    assert '&lt;p&gt;' not in content


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_plain_text_email_is_shown_as_paragraphs(organizer_client, order):
    """A plain-text system email is shown as paragraphs, like the HTML email."""
    log_email(order, 'eventyay.event.order.email.resend', 'Hello,\n\nyour order is confirmed.')

    content = organizer_client.get(order_url(order) + 'mail_history').content.decode()

    assert '<p>Hello,</p>' in content
    assert '<p>your order is confirmed.</p>' in content


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_email_is_shown_in_a_grey_box(organizer_client, order):
    """The email keeps the grey box it had as a <pre> block, using the Bootstrap well."""
    log_email(order, 'eventyay.event.order.email.resend', 'Hello,\n\nyour order is confirmed.')

    content = organizer_client.get(order_url(order) + 'mail_history').content.decode()

    assert '<div class="mail-body well well-sm"><p>Hello,</p>' in content


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_email_html_is_sanitized(organizer_client, order):
    """Unsafe HTML in a stored email is removed before it is shown."""
    log_email(order, 'eventyay.event.order.email.custom_sent', '<p>Hi</p><script>alert(1)</script>')

    content = organizer_client.get(order_url(order) + 'mail_history').content.decode()

    assert '<p>Hi</p>' in content
    assert '<script>alert(1)' not in content


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_remote_images_are_shown_as_links(organizer_client, order):
    """Remote images are shown as links, while inline data images are still shown."""
    qr_image = 'data:image/png;base64,iVBORw0KGgo='
    log_email(
        order,
        'eventyay.event.order.email.custom_sent',
        f'<p><img src="https://images.example.com/banner.png" alt="Banner"></p><p><img src="{qr_image}" alt="QR"></p>',
    )

    content = organizer_client.get(order_url(order) + 'mail_history').content.decode()

    assert '<img alt="Banner"' not in content
    assert 'src="https://images.example.com/banner.png"' not in content
    assert 'href="https://images.example.com/banner.png"' in content
    assert '>Banner</a>' in content
    assert f'src="{qr_image}"' in content


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
@pytest.mark.parametrize(
    'src',
    [
        ' https://images.example.com/banner.png',
        '&#10;https://images.example.com/banner.png',
        '/\\images.example.com/banner.png',
    ],
    ids=['leading-space', 'leading-newline', 'backslash-path'],
)
def test_images_with_disguised_sources_are_shown_as_links(organizer_client, order, src):
    """Images whose source a browser would still load from another host are shown as links too."""
    log_email(order, 'eventyay.event.order.email.custom_sent', f'<p><img src="{src}" alt="Banner"></p>')

    content = organizer_client.get(order_url(order) + 'mail_history').content.decode()

    assert '>Banner</a>' in content
    assert 'images.example.com/banner.png"/>' not in content
    assert '<img alt="Banner"' not in content

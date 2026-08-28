import datetime

import pytest
from django.urls import reverse
from django.utils import timezone
from django_scopes import scopes_disabled

from eventyay.base.models import Event, Order


@pytest.mark.django_db
def test_my_orders_view_apply_button_tooltip_and_fields(client, user, event):
    client.force_login(user)
    with scopes_disabled():
        Order.objects.create(
            code="ORD123",
            status=Order.STATUS_PAID,
            datetime=timezone.now(),
            expires=timezone.now() + datetime.timedelta(days=1),
            total=10,
            event=event,
            email=user.email,
        )

    url = reverse("eventyay_common:orders")
    response = client.get(url)
    assert response.status_code == 200

    content = response.content.decode()
    assert 'title="Apply filters"' in content
    assert 'name="event"' in content
    assert 'name="code"' in content
    assert 'name="status"' in content
    assert 'name="date_from"' in content
    assert 'name="date_to"' in content


@pytest.mark.django_db
def test_user_orders_filtering_by_event(client, user, event, organizer):
    client.force_login(user)
    with scopes_disabled():
        event2 = Event.objects.create(
            organizer=organizer,
            name="Event 2",
            slug="event-2",
            date_from=timezone.now(),
            live=True,
            is_public=True,
        )
        order1 = Order.objects.create(
            code="ORD001",
            status=Order.STATUS_PAID,
            datetime=timezone.now(),
            expires=timezone.now() + datetime.timedelta(days=1),
            total=10,
            event=event,
            email=user.email,
        )
        order2 = Order.objects.create(
            code="ORD002",
            status=Order.STATUS_PAID,
            datetime=timezone.now(),
            expires=timezone.now() + datetime.timedelta(days=1),
            total=20,
            event=event2,
            email=user.email,
        )

    url = reverse("eventyay_common:orders")
    response = client.get(f"{url}?event={event.pk}")
    assert response.status_code == 200
    orders = list(response.context["order_list"])
    assert order1 in orders
    assert order2 not in orders


@pytest.mark.django_db
def test_user_orders_filtering_by_code_partial_and_normalized(client, user, event):
    client.force_login(user)
    with scopes_disabled():
        order1 = Order.objects.create(
            code="ABC12345",
            status=Order.STATUS_PAID,
            datetime=timezone.now(),
            expires=timezone.now() + datetime.timedelta(days=1),
            total=10,
            event=event,
            email=user.email,
        )
        order2 = Order.objects.create(
            code="XYZ67890",
            status=Order.STATUS_PAID,
            datetime=timezone.now(),
            expires=timezone.now() + datetime.timedelta(days=1),
            total=20,
            event=event,
            email=user.email,
        )

    url = reverse("eventyay_common:orders")

    # Partial code match
    response = client.get(f"{url}?code=ABC123")
    assert response.status_code == 200
    orders = list(response.context["order_list"])
    assert order1 in orders
    assert order2 not in orders

    # Case-insensitive match
    response = client.get(f"{url}?code=abc123")
    assert response.status_code == 200
    orders = list(response.context["order_list"])
    assert order1 in orders
    assert order2 not in orders


@pytest.mark.django_db
def test_user_orders_filtering_by_status(client, user, event):
    client.force_login(user)
    with scopes_disabled():
        order_paid = Order.objects.create(
            code="PAID01",
            status=Order.STATUS_PAID,
            datetime=timezone.now(),
            expires=timezone.now() + datetime.timedelta(days=1),
            total=10,
            event=event,
            email=user.email,
        )
        order_pending = Order.objects.create(
            code="PEND01",
            status=Order.STATUS_PENDING,
            datetime=timezone.now(),
            expires=timezone.now() + datetime.timedelta(days=1),
            total=10,
            event=event,
            email=user.email,
        )

    url = reverse("eventyay_common:orders")

    # Filter paid
    response = client.get(f"{url}?status={Order.STATUS_PAID}")
    assert response.status_code == 200
    orders = list(response.context["order_list"])
    assert order_paid in orders
    assert order_pending not in orders

    # Filter pending
    response = client.get(f"{url}?status={Order.STATUS_PENDING}")
    assert response.status_code == 200
    orders = list(response.context["order_list"])
    assert order_pending in orders
    assert order_paid not in orders


@pytest.mark.django_db
def test_user_orders_filtering_by_date_from_and_date_to(client, user, event):
    client.force_login(user)
    now = timezone.now()
    dt_early = now - datetime.timedelta(days=20)
    dt_mid = now - datetime.timedelta(days=10)
    dt_late = now - datetime.timedelta(days=2)

    with scopes_disabled():
        order_early = Order.objects.create(
            code="EARLY1",
            status=Order.STATUS_PAID,
            datetime=dt_early,
            expires=dt_early + datetime.timedelta(days=1),
            total=10,
            event=event,
            email=user.email,
        )
        order_mid = Order.objects.create(
            code="MID001",
            status=Order.STATUS_PAID,
            datetime=dt_mid,
            expires=dt_mid + datetime.timedelta(days=1),
            total=10,
            event=event,
            email=user.email,
        )
        order_late = Order.objects.create(
            code="LATE01",
            status=Order.STATUS_PAID,
            datetime=dt_late,
            expires=dt_late + datetime.timedelta(days=1),
            total=10,
            event=event,
            email=user.email,
        )

    url = reverse("eventyay_common:orders")

    date_from_str = (dt_mid - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    date_to_str = (dt_mid + datetime.timedelta(days=1)).strftime("%Y-%m-%d")

    # Filter by date_from and date_to around mid date
    response = client.get(f"{url}?date_from={date_from_str}&date_to={date_to_str}")
    assert response.status_code == 200
    orders = list(response.context["order_list"])
    assert order_mid in orders
    assert order_early not in orders
    assert order_late not in orders


@pytest.mark.django_db
def test_user_orders_combined_filters(client, user, event):
    client.force_login(user)
    now = timezone.now()
    with scopes_disabled():
        order_target = Order.objects.create(
            code="MATCH1",
            status=Order.STATUS_PAID,
            datetime=now,
            expires=now + datetime.timedelta(days=1),
            total=10,
            event=event,
            email=user.email,
        )
        order_other = Order.objects.create(
            code="MATCH2",
            status=Order.STATUS_PENDING,
            datetime=now,
            expires=now + datetime.timedelta(days=1),
            total=10,
            event=event,
            email=user.email,
        )

    url = reverse("eventyay_common:orders")
    today_str = now.strftime("%Y-%m-%d")
    response = client.get(
        f"{url}?event={event.pk}&code=MATCH1&status={Order.STATUS_PAID}&date_from={today_str}&date_to={today_str}"
    )
    assert response.status_code == 200
    orders = list(response.context["order_list"])
    assert order_target in orders
    assert order_other not in orders


@pytest.mark.django_db
def test_user_orders_invalid_filter_param_redirect(client, user, event):
    client.force_login(user)
    url = reverse("eventyay_common:orders")
    response = client.get(f"{url}?date_from=invalid-date&code=TEST")
    assert response.status_code == 302
    assert "code=TEST" in response.url
    assert "date_from" not in response.url

import pytest
from unittest.mock import patch

from django.db.models.query import QuerySet
from django_scopes import scope

from eventyay.base.models import SubmitterAccessCode


@pytest.mark.django_db
def test_wizard_access_code_select_for_update(client, event, access_code):
    access_code.maximum_uses = 1
    access_code.save()

    original_sfu = QuerySet.select_for_update

    def mock_sfu(queryset, *args, **kwargs):
        if queryset.model == SubmitterAccessCode:
            mock_sfu.called = True
        return original_sfu(queryset, *args, **kwargs)

    mock_sfu.called = False

    with patch('django.db.models.query.QuerySet.select_for_update', new=mock_sfu):
        with scope(event=event):
            url = f"/{event.organizer.slug}/{event.slug}/submit/info/?access_code={access_code.code}"
            client.get(url)

    assert mock_sfu.called, "select_for_update() was not called on the access code queryset"

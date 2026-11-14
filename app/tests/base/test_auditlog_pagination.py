import datetime
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from eventyay.base.models.audit import AuditLog
from eventyay.base.models.auth import User
from eventyay.base.services.event import get_audit_log
from eventyay.features.live.modules.event import EventModule


def test_auditlog_serialize_public_with_user():
    user = User(id=uuid.uuid4(), profile={"display_name": "Test User"})
    log = AuditLog(
        id=1,
        user=user,
        type="room.create",
        data={"name": "Demo Room"},
    )
    with patch.object(AuditLog, "timestamp", create=True):
        log.timestamp = datetime.datetime(2026, 1, 1, 12, 0, 0, tzinfo=datetime.UTC)
        serialized = log.serialize_public()

        assert serialized["id"] == 1
        assert serialized["type"] == "room.create"
        assert serialized["data"] == {"name": "Demo Room"}
        assert serialized["user"]["id"] == str(user.id)
        assert serialized["user"]["profile"]["display_name"] == "Test User"


def test_auditlog_serialize_public_with_null_user():
    log = AuditLog(
        id=2,
        user=None,
        type="system.maintenance",
        data={"status": "ok"},
    )
    with patch.object(AuditLog, "timestamp", create=True):
        log.timestamp = datetime.datetime(2026, 1, 1, 12, 0, 0, tzinfo=datetime.UTC)
        serialized = log.serialize_public()

        assert serialized["id"] == 2
        assert serialized["type"] == "system.maintenance"
        assert serialized["data"] == {"status": "ok"}
        assert serialized["user"] is None


@pytest.mark.asyncio
async def test_event_module_auditlog_get_extracts_params():
    consumer = MagicMock()
    consumer.user = MagicMock()
    consumer.event = MagicMock()
    consumer.event.id = "sample_event_id"
    consumer.event.has_permission_async = AsyncMock(return_value=True)
    consumer.send_success = AsyncMock()

    module = EventModule(consumer)

    fake_result = {
        "results": [{"id": 1, "type": "room.create"}],
        "total": 1,
        "page": 2,
        "total_pages": 5,
        "page_size": 25,
        "isLastPage": False,
    }

    mock_getter = AsyncMock(return_value=fake_result)
    with patch("eventyay.features.live.modules.event.get_audit_log", new=mock_getter) as mock_get:
        await module.auditlog_get({
            "page": 2,
            "page_size": 25,
            "search": "test",
            "order": "asc",
        })

        mock_get.assert_awaited_once_with(
            consumer.event,
            page=2,
            page_size=25,
            search="test",
            order="asc",
        )
        consumer.send_success.assert_awaited_once_with(fake_result)


@pytest.mark.asyncio
async def test_event_module_auditlog_get_defaults():
    consumer = MagicMock()
    consumer.user = MagicMock()
    consumer.event = MagicMock()
    consumer.event.has_permission_async = AsyncMock(return_value=True)
    consumer.send_success = AsyncMock()

    module = EventModule(consumer)

    fake_result = {
        "results": [],
        "total": 0,
        "page": 1,
        "total_pages": 1,
        "page_size": 50,
        "isLastPage": True,
    }

    mock_getter = AsyncMock(return_value=fake_result)
    with patch("eventyay.features.live.modules.event.get_audit_log", new=mock_getter) as mock_get:
        await module.auditlog_get(None)

        mock_get.assert_awaited_once_with(
            consumer.event,
            page=1,
            page_size=50,
            search="",
            order="desc",
        )
        consumer.send_success.assert_awaited_once_with(fake_result)


@pytest.mark.asyncio
async def test_get_audit_log_service_pagination():
    event = MagicMock()
    event.id = "event_123"

    mock_qs = MagicMock()
    mock_qs.prefetch_related.return_value = mock_qs
    mock_qs.order_by.return_value = mock_qs

    mock_items = []
    for i in range(75):
        m = MagicMock()
        m.serialize_public.return_value = {"id": i, "type": f"action.{i}"}
        mock_items.append(m)

    mock_qs.count.return_value = len(mock_items)
    mock_qs.__len__.return_value = len(mock_items)
    mock_qs.__getitem__.side_effect = lambda s: mock_items[s]

    with patch.object(AuditLog.objects, "filter", return_value=mock_qs):
        result_page1 = await get_audit_log(event, page=1, page_size=25, order="desc")
        assert result_page1["total"] == 75
        assert result_page1["total_pages"] == 3
        assert result_page1["page"] == 1
        assert result_page1["page_size"] == 25
        assert result_page1["isLastPage"] is False
        assert len(result_page1["results"]) == 25
        assert result_page1["results"][0]["id"] == 0

        result_page3 = await get_audit_log(event, page=3, page_size=25, order="desc")
        assert result_page3["page"] == 3
        assert result_page3["isLastPage"] is True
        assert len(result_page3["results"]) == 25

        mock_qs.order_by.assert_called_with("-timestamp", "-id")


@pytest.mark.asyncio
async def test_get_audit_log_service_search_and_asc_order():
    event = MagicMock()
    event.id = "event_123"

    mock_qs = MagicMock()
    mock_qs.prefetch_related.return_value = mock_qs
    mock_qs.annotate.return_value = mock_qs
    mock_qs.filter.return_value = mock_qs
    mock_qs.order_by.return_value = mock_qs
    mock_qs.count.return_value = 0
    mock_qs.__len__.return_value = 0
    mock_qs.__getitem__.side_effect = lambda s: []

    with patch.object(AuditLog.objects, "filter", return_value=mock_qs):
        result = await get_audit_log(event, page=1, page_size=50, search="my_search", order="asc")

        assert result["total"] == 0
        assert result["isLastPage"] is True
        mock_qs.annotate.assert_called_once()
        mock_qs.filter.assert_called_once()
        mock_qs.order_by.assert_called_with("timestamp", "id")


@pytest.mark.asyncio
async def test_get_audit_log_invalid_page():
    event = MagicMock()
    event.id = "event_123"

    mock_qs = MagicMock()
    mock_qs.prefetch_related.return_value = mock_qs
    mock_qs.order_by.return_value = mock_qs
    mock_qs.count.return_value = 10
    mock_qs.__len__.return_value = 10
    mock_qs.__getitem__.side_effect = lambda s: []

    with patch.object(AuditLog.objects, "filter", return_value=mock_qs):
        result = await get_audit_log(event, page=999, page_size=50)

        assert result["total"] == 10
        assert result["page"] == 999
        assert result["results"] == []
        assert result["isLastPage"] is True


@pytest.mark.asyncio
async def test_event_module_auditlog_get_invalid_body_shape():
    consumer = MagicMock()
    consumer.user = MagicMock()
    consumer.event = MagicMock()
    consumer.event.has_permission_async = AsyncMock(return_value=True)
    consumer.send_error = AsyncMock()

    module = EventModule(consumer)

    with patch("eventyay.features.live.modules.event.get_audit_log") as mock_get:
        await module.auditlog_get("not-a-dict")
        consumer.send_error.assert_awaited_once_with("command.error", "Invalid request body")
        mock_get.assert_not_called()


@pytest.mark.asyncio
async def test_get_audit_log_service_page_size_capping():
    event = MagicMock()
    event.id = "event_123"

    mock_qs = MagicMock()
    mock_qs.prefetch_related.return_value = mock_qs
    mock_qs.order_by.return_value = mock_qs
    mock_qs.count.return_value = 0
    mock_qs.__len__.return_value = 0
    mock_qs.__getitem__.side_effect = lambda s: []

    with patch.object(AuditLog.objects, "filter", return_value=mock_qs):
        # 200 should be allowed
        result = await get_audit_log(event, page=1, page_size=200)
        assert result["page_size"] == 200

        # > 200 should be capped at 200
        result_capped = await get_audit_log(event, page=1, page_size=500)
        assert result_capped["page_size"] == 200


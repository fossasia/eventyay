from unittest.mock import AsyncMock, MagicMock

import pytest
from django_scopes import scope

from eventyay.base.models import Room
from eventyay.base.models.poll import Poll
from eventyay.base.models.roomquestion import QuestionVote, RoomQuestion
from eventyay.base.services.question import vote_on_question
from eventyay.features.live import decorators
from eventyay.features.live.exceptions import ConsumerException
from eventyay.features.live.modules import poll as poll_module
from eventyay.features.live.modules import question as question_module
from eventyay.features.live.modules.poll import PollModule
from eventyay.features.live.modules.question import (
    MAX_QUESTION_LENGTH,
    QuestionModule,
    clean_question_content,
)


@pytest.mark.parametrize('content', ['', '   ', '\n\t ', None, 42, ['Why?']])
def test_clean_question_content_rejects_blank(content):
    with pytest.raises(ConsumerException) as excinfo:
        clean_question_content(content)
    assert excinfo.value.code == 'question.empty'


def test_clean_question_content_rejects_too_long():
    with pytest.raises(ConsumerException) as excinfo:
        clean_question_content('a' * (MAX_QUESTION_LENGTH + 1))
    assert excinfo.value.code == 'question.too_long'


def test_clean_question_content_trims_and_keeps_text_at_limit():
    assert clean_question_content('  Why?\n') == 'Why?'
    at_limit = 'a' * MAX_QUESTION_LENGTH
    assert clean_question_content(f'  {at_limit}  ') == at_limit


def make_module(module_class, module_type, monkeypatch):
    """A live module for a user who has every permission in an in-memory room."""
    room = Room(
        pk=1,
        name='Stage',
        module_config=[{'type': module_type, 'config': {'active': True}}],
    )
    room.refresh_from_db_if_outdated = AsyncMock()
    monkeypatch.setattr(
        decorators,
        'check_video_entitlements',
        lambda event, modules: MagicMock(allowed=True),
    )
    consumer = MagicMock()
    consumer.event.has_permission_async = AsyncMock(return_value=True)
    consumer.room_cache = {'1': room}
    consumer.send_success = AsyncMock()
    consumer.send_error = AsyncMock()
    consumer.channel_layer.group_send = AsyncMock()
    consumer.channel_layer.group_add = AsyncMock()
    return module_class(consumer), consumer


@pytest.mark.asyncio
@pytest.mark.django_db
@pytest.mark.parametrize('content', ['', '   '])
async def test_ask_blank_question_is_not_stored(content, monkeypatch):
    module, consumer = make_module(QuestionModule, 'question', monkeypatch)
    create = AsyncMock()
    monkeypatch.setattr(question_module, 'create_question', create)

    with pytest.raises(ConsumerException) as excinfo:
        await module.ask_question({'room': '1', 'content': content})

    assert excinfo.value.code == 'question.empty'
    create.assert_not_awaited()
    consumer.send_success.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_ask_question_stores_trimmed_text(monkeypatch):
    module, consumer = make_module(QuestionModule, 'question', monkeypatch)
    create = AsyncMock(return_value={'id': 'q1', 'content': 'Why?', 'state': 'mod_queue'})
    monkeypatch.setattr(question_module, 'create_question', create)

    await module.ask_question({'room': '1', 'content': '  Why?  '})

    assert create.await_args.kwargs['content'] == 'Why?'
    consumer.send_success.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_vote_on_unknown_question_reports_error(monkeypatch):
    module, consumer = make_module(QuestionModule, 'question', monkeypatch)
    monkeypatch.setattr(
        question_module,
        'vote_on_question',
        AsyncMock(side_effect=RoomQuestion.DoesNotExist),
    )

    await module.vote({'room': '1', 'id': 'q1', 'vote': True})

    consumer.send_error.assert_awaited_once_with('question.unknown', message='This question no longer exists.')
    consumer.channel_layer.group_send.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_vote_on_closed_poll_reports_error(monkeypatch):
    module, consumer = make_module(PollModule, 'poll', monkeypatch)
    monkeypatch.setattr(poll_module, 'vote_on_poll', AsyncMock(side_effect=Poll.DoesNotExist))

    await module.vote({'room': '1', 'id': 'p1', 'options': ['o1']})

    consumer.send_error.assert_awaited_once_with('poll.closed', message='This poll is no longer open for voting.')
    consumer.channel_layer.group_send.assert_not_awaited()


@pytest.mark.django_db
def test_vote_on_question_from_another_room_is_not_stored(event, room, user):
    with scope(event=event):
        other_room = Room.objects.create(event=event, name='Other room', position=2)
    question = RoomQuestion.objects.create(
        room=other_room, sender=user, content='Why?', state=RoomQuestion.States.VISIBLE
    )

    with pytest.raises(RoomQuestion.DoesNotExist):
        vote_on_question.func(pk=question.pk, room=room, user=user, vote=True)

    assert not QuestionVote.objects.filter(question=question).exists()


@pytest.mark.django_db
def test_vote_on_question_counts_vote(event, room, user):
    question = RoomQuestion.objects.create(room=room, sender=user, content='Why?', state=RoomQuestion.States.VISIBLE)

    result = vote_on_question.func(pk=question.pk, room=room, user=user, vote=True)
    assert result['score'] == 1

    result = vote_on_question.func(pk=question.pk, room=room, user=user, vote=False)
    assert result['score'] == 0

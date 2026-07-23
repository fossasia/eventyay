from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlparse

import pytest
from django.http import HttpResponse
from django.test import RequestFactory, override_settings
from django_scopes import scope

from eventyay.base.middleware import SecurityMiddleware, _parse_csp
from eventyay.base.models import Answer, TalkQuestion, TalkQuestionTarget, TalkQuestionVariant
from eventyay.common.video_embed import get_video_embed_info


def _assert_youtube_embed(embed_url, video_id, *, start=None):
    parsed = urlparse(embed_url)
    assert parsed.scheme == 'https'
    assert parsed.netloc == 'www.youtube-nocookie.com'
    assert parsed.path == f'/embed/{video_id}'
    query = parse_qs(parsed.query)
    assert query.get('autoplay') == ['0']
    if start is None:
        assert 'start' not in query
    else:
        assert query.get('start') == [str(start)]


def _assert_vimeo_embed(embed_url, video_id, *, time_hash=None):
    parsed = urlparse(embed_url)
    assert parsed.scheme == 'https'
    assert parsed.netloc == 'player.vimeo.com'
    assert parsed.path == f'/video/{video_id}'
    query = parse_qs(parsed.query)
    assert query.get('autoplay') == ['0']
    if time_hash is None:
        assert parsed.fragment == ''
    else:
        assert parsed.fragment == time_hash


@pytest.mark.parametrize(
    'url,video_id,start',
    (
        ('https://www.youtube.com/watch?v=dQw4w9WgXcQ', 'dQw4w9WgXcQ', None),
        ('https://youtu.be/dQw4w9WgXcQ', 'dQw4w9WgXcQ', None),
        ('https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=90', 'dQw4w9WgXcQ', 90),
        ('https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=1m30s', 'dQw4w9WgXcQ', 90),
        ('https://www.youtube.com/watch?v=dQw4w9WgXcQ&start=125', 'dQw4w9WgXcQ', 125),
        ('https://youtu.be/dQw4w9WgXcQ?t=45', 'dQw4w9WgXcQ', 45),
        ('https://youtu.be/dQw4w9WgXcQ?t=1h2m3s', 'dQw4w9WgXcQ', 3723),
        ('https://www.youtube.com/watch?v=dQw4w9WgXcQ#t=30', 'dQw4w9WgXcQ', 30),
        ('https://www.youtube.com/embed/dQw4w9WgXcQ?start=15', 'dQw4w9WgXcQ', 15),
        ('https://www.youtube.com/shorts/dQw4w9WgXcQ?t=12', 'dQw4w9WgXcQ', 12),
        ('http://m.youtube.com/watch?v=dQw4w9WgXcQ&t=8s', 'dQw4w9WgXcQ', 8),
    ),
)
def test_youtube_embed_preserves_timestamp_and_disables_autoplay(url, video_id, start):
    info = get_video_embed_info(url)
    assert info is not None
    assert info['provider'] == 'youtube'
    _assert_youtube_embed(info['embed_url'], video_id, start=start)
    assert 'https://www.youtube-nocookie.com' in info['csp_origins']


@pytest.mark.parametrize(
    'url,video_id,time_hash',
    (
        ('https://vimeo.com/123456789', '123456789', None),
        ('https://player.vimeo.com/video/123456789', '123456789', None),
        ('https://vimeo.com/123456789#t=1m30s', '123456789', 't=1m30s'),
        ('https://vimeo.com/123456789#t=90s', '123456789', 't=90s'),
        ('https://vimeo.com/123456789?t=75', '123456789', 't=75s'),
        ('https://player.vimeo.com/video/123456789#t=10s', '123456789', 't=10s'),
    ),
)
def test_vimeo_embed_preserves_timestamp_and_disables_autoplay(url, video_id, time_hash):
    info = get_video_embed_info(url)
    assert info is not None
    assert info['provider'] == 'vimeo'
    _assert_vimeo_embed(info['embed_url'], video_id, time_hash=time_hash)
    assert info['csp_origins'] == ['https://player.vimeo.com']


@pytest.mark.parametrize(
    'url',
    (
        '',
        'not-a-url',
        'ftp://example.com/video',
        None,
        'https://example.com/embed/player',
        'https://example.com/watch?v=nope',
        'https://www.youtube.com/watch?v=',
        'https://vimeo.com/not-a-number',
    ),
)
def test_get_video_embed_info_rejects_invalid(url):
    assert get_video_embed_info(url) is None


@pytest.mark.django_db
def test_video_answer_string(event):
    with scope(event=event):
        question = TalkQuestion.objects.create(
            question='Recording',
            variant=TalkQuestionVariant.VIDEO,
            event=event,
        )
        answer = Answer.objects.create(
            question=question,
            answer='https://youtu.be/dQw4w9WgXcQ?t=90',
        )
        assert answer.answer_string == 'https://youtu.be/dQw4w9WgXcQ?t=90'


@pytest.mark.django_db
def test_schedule_public_video_answer_includes_timestamped_embed_url(event, slot):
    with scope(event=event):
        question = TalkQuestion.objects.create(
            question='Session video',
            variant=TalkQuestionVariant.VIDEO,
            event=event,
            is_public=True,
            target=TalkQuestionTarget.SUBMISSION,
        )
        Answer.objects.create(
            question=question,
            submission=slot.submission,
            answer='https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=1m30s',
        )
        # Regular URL fields must never produce embed_url, even for YouTube links
        url_question = TalkQuestion.objects.create(
            question='Slides URL',
            variant=TalkQuestionVariant.URL,
            event=event,
            is_public=True,
            target=TalkQuestionTarget.SUBMISSION,
        )
        Answer.objects.create(
            question=url_question,
            submission=slot.submission,
            answer='https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=30',
        )

        data = slot.schedule.build_data(enrich=True)
        talk = next(t for t in data['talks'] if t.get('code') == slot.submission.code)
        video_answers = [a for a in talk['answers'] if a.get('variant') == 'video']
        url_answers = [a for a in talk['answers'] if a.get('variant') == 'url']

        assert len(video_answers) == 1
        _assert_youtube_embed(video_answers[0]['embed_url'], 'dQw4w9WgXcQ', start=90)
        assert len(url_answers) == 1
        assert 'embed_url' not in url_answers[0]


@pytest.mark.django_db
def test_private_video_answer_not_in_schedule(event, slot):
    with scope(event=event):
        question = TalkQuestion.objects.create(
            question='Private video',
            variant=TalkQuestionVariant.VIDEO,
            event=event,
            is_public=False,
            target=TalkQuestionTarget.SUBMISSION,
        )
        Answer.objects.create(
            question=question,
            submission=slot.submission,
            answer='https://youtu.be/dQw4w9WgXcQ?t=10',
        )
        data = slot.schedule.build_data(enrich=True)
        talk = next(t for t in data['talks'] if t.get('code') == slot.submission.code)
        assert talk['answers'] == []


@override_settings(SITE_URL='https://example.com')
@patch('eventyay.base.middleware.global_settings_object')
def test_security_middleware_applies_csp_update(mock_global_settings):
    mock_gs = MagicMock()
    mock_gs.settings.leaflet_tiles = None
    mock_global_settings.return_value = mock_gs

    factory = RequestFactory()
    middleware = SecurityMiddleware(lambda request: HttpResponse('ok'))
    request = factory.get('/talk/demo/')
    request.organizer = None
    request.event = None
    response = HttpResponse('ok')
    response._csp_update = {'frame-src': ['https://www.youtube-nocookie.com', 'https://player.vimeo.com']}
    result = middleware.process_response(request, response)
    frame_src = _parse_csp(result['Content-Security-Policy'])['frame-src']
    assert 'https://www.youtube-nocookie.com' in frame_src
    assert 'https://player.vimeo.com' in frame_src

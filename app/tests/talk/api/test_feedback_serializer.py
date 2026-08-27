from types import SimpleNamespace

from eventyay.api.serializers.feedback import AuthorSerializer


def test_author_serializer_uses_display_name_and_avatar_url():
    user = SimpleNamespace(
        code='speaker-1',
        get_display_name=lambda: 'Jane Speaker',
        avatar_url='https://example.com/avatar.png',
    )
    data = AuthorSerializer(user).data
    assert data == {
        'code': 'speaker-1',
        'name': 'Jane Speaker',
        'avatar': 'https://example.com/avatar.png',
    }

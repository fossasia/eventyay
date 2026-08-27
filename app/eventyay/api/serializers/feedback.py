from rest_framework import serializers

from eventyay.api.serializers.i18n import I18nAwareModelSerializer
from eventyay.api.versions import CURRENT_VERSIONS, register_serializer
from eventyay.base.models import Feedback, User


class AuthorSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    avatar = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('code', 'name', 'avatar')

    def get_name(self, obj):
        return obj.get_display_name()

    def get_avatar(self, obj):
        return obj.avatar_url or ''


@register_serializer(versions=CURRENT_VERSIONS)
class FeedbackReplySerializer(I18nAwareModelSerializer):
    author = serializers.SerializerMethodField()

    class Meta:
        model = Feedback
        fields = (
            'id', 'talk', 'speaker', 'rating', 'review', 'author',
            'is_public', 'status', 'parent', 'created', 'updated'
        )
        read_only_fields = ('author', 'status', 'created', 'updated', 'is_public')

    def get_author(self, obj):
        if not obj.is_public:
            return None
        if not obj.author:
            return None
        return AuthorSerializer(obj.author).data


@register_serializer(versions=CURRENT_VERSIONS)
class FeedbackSerializer(I18nAwareModelSerializer):
    author = serializers.SerializerMethodField()
    replies = serializers.SerializerMethodField()

    class Meta:
        model = Feedback
        fields = (
            'id', 'talk', 'speaker', 'rating', 'review', 'author',
            'is_public', 'status', 'parent', 'created', 'updated', 'replies'
        )
        read_only_fields = ('author', 'status', 'created', 'updated')

    def get_author(self, obj):
        if not obj.is_public:
            return None
        if not obj.author:
            return None
        return AuthorSerializer(obj.author).data

    def get_replies(self, obj):
        if obj.parent_id is None:
            replies = obj.replies.filter(status='published').order_by('created')
            return FeedbackReplySerializer(replies, many=True).data
        return []

from django.db.models import Q
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
        """Return published replies visible to organisers or their target speakers."""
        if obj.parent_id is None:
            replies = obj.replies.filter(status='published').select_related('author').order_by('created')
            request = self.context.get('request')
            if not request or not request.user.has_perm('base.orga_list_submission', request.event):
                if request and request.user.is_authenticated:
                    replies = replies.filter(
                        Q(is_public=True)
                        | (Q(talk__speakers=request.user) & (Q(speaker=request.user) | Q(speaker__isnull=True)))
                    ).distinct()
                else:
                    replies = replies.filter(is_public=True)
            return FeedbackReplySerializer(replies, many=True, context=self.context).data
        return []

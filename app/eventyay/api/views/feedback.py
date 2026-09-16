from django.db import models
from drf_spectacular.utils import extend_schema_view
from rest_framework import mixins, viewsets
from rest_framework.exceptions import PermissionDenied, ValidationError

from eventyay.agenda.feedback_access import (
    feedback_is_public_for_submission,
    get_feedback_anonymous_mode,
    user_can_give_feedback,
)
from eventyay.api.mixins import PretalxViewSetMixin
from eventyay.api.serializers.feedback import FeedbackSerializer
from eventyay.api.auth.permission import EventPermission
from rest_framework.permissions import SAFE_METHODS
from eventyay.base.models import Feedback

class FeedbackPermission(EventPermission):
    def _has_event_permission(
        self, request, perm_holder, required_permission, event_slug, organizer_slug=None, *, allow_public_read=False
    ):
        request.event = self._resolve_event(event_slug, organizer_slug=organizer_slug)
        if not request.event:
            return False

        request.organizer = request.event.organizer

        if request.user.is_authenticated and request.method in SAFE_METHODS:
            request.eventpermset = set()
            return True

        if request.method == 'POST' and request.user.is_authenticated:
            request.eventpermset = set()
            return True

        if not perm_holder.has_event_permission(
            request.event.organizer, request.event, request=request
        ):
            return False

        self._set_eventpermset(request, perm_holder)
        return self._has_required_permission(required_permission, request.eventpermset)

class FeedbackViewSet(
    PretalxViewSetMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = (FeedbackPermission,)
    serializer_class = FeedbackSerializer
    queryset = Feedback.objects.none()
    
    # We don't define endpoint = 'feedback' if we just register it in router.
    # But PretalxViewSetMixin might use self.endpoint.
    endpoint = 'feedback'

    def get_queryset(self):
        if not self.event:
            return self.queryset
        
        qs = Feedback.objects.filter(talk__event=self.event)
        
        # We only want top-level comments when listing (replies are nested)
        if self.action == 'list':
            qs = qs.filter(parent__isnull=True)
        
        talk_code = self.request.query_params.get('talk')
        if talk_code:
            qs = qs.filter(talk__code=talk_code)
            
        if not self.request.user.has_perm('base.orga_list_submission', self.event):
            # Only published, OR authored by the user
            if self.request.user.is_authenticated:
                qs = qs.filter(models.Q(status='published') | models.Q(author=self.request.user))
            else:
                qs = qs.filter(status='published')
                
        # Only show public comments in the public API unless you're orga
        if not self.request.user.has_perm('base.orga_list_submission', self.event):
             qs = qs.filter(is_public=True)

        return qs.order_by('-created')

    def perform_create(self, serializer):
        if not self.event.get_feature_flag('use_feedback'):
            raise PermissionDenied('Feedback is not enabled for this event.')

        user = self.request.user
        if not user.is_authenticated:
            raise PermissionDenied('You must be logged in to comment.')

        talk = serializer.validated_data.get('talk')
        if not talk:
            raise ValidationError({'talk': 'This field is required.'})

        if not user_can_give_feedback(user, talk):
            raise PermissionDenied('You are not allowed to comment on this session.')

        is_public = feedback_is_public_for_submission(
            self.event,
            serializer.validated_data.get('is_public', True),
        )
        if not is_public and get_feedback_anonymous_mode(self.event) == 'public':
            raise PermissionDenied('Anonymous feedback is not allowed.')

        status = 'published'
        if is_public and self.event.get_feature_flag('feedback_require_review'):
            status = 'pending'

        serializer.save(
            author=user,
            is_public=is_public,
            status=status,
        )

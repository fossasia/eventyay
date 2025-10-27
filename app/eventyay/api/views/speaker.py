from django.utils.functional import cached_property
from django_scopes import scopes_disabled
from rest_framework import mixins, viewsets
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny

from eventyay.base.models.profile import SpeakerProfile
from eventyay.api.serializers.speaker import SpeakerSerializer


class LargeResultsSetPagination(PageNumberPagination):
    """Pagination class that supports a 'limit' query parameter."""
    page_size = 50
    page_size_query_param = 'limit'
    max_page_size = 10000


class SpeakerViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """
    API endpoint for listing and retrieving speakers for an event.
    """
    serializer_class = SpeakerSerializer
    queryset = SpeakerProfile.objects.none()
    lookup_field = "user__code__iexact"
    pagination_class = LargeResultsSetPagination
    permission_classes = [AllowAny]  # Allow public access to speakers list

    def get_queryset(self):
        """Return speakers for the current event."""
        if not hasattr(self.request, 'event') or not self.request.event:
            return self.queryset

        # Use scopes_disabled to bypass django_scopes since we're filtering by event explicitly
        with scopes_disabled():
            # Get all speaker profiles for this event that have a user
            queryset = SpeakerProfile.objects.filter(
                event=self.request.event,
                user__isnull=False
            ).select_related('user', 'event').order_by('user__fullname')

            return queryset

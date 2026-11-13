from django.db import transaction
from django.shortcuts import get_object_or_404
from django_scopes import scope
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from rest_framework import exceptions, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from eventyay.api.documentation import build_expand_docs, build_search_docs
from eventyay.api.mixins import PretalxViewSetMixin
from eventyay.api.serializers.team import TeamInviteSerializer, TeamSerializer
from eventyay.api.views.organizer import check_api_team_delegation, team_delegation_actor
from eventyay.base.models.auth import User
from eventyay.base.models.organizer import (
    Team,
    TeamInvite,
    TeamPermissionError,
    check_access_permissions,
)
from eventyay.base.services.team_permissions import lock_team_organizer
from eventyay.base.services.teams import TeamInviteDelegationError, TeamInviteError, invite_to_team


class TeamInviteCreateSerializer(serializers.Serializer):
    email = serializers.EmailField()


class TeamMemberRemoveSerializer(serializers.Serializer):
    user_code = serializers.CharField()


@extend_schema_view(
    list=extend_schema(
        summary='List Teams',
        tags=['teams'],
        parameters=[
            build_search_docs('name'),
            build_expand_docs('members', 'invites', 'limit_tracks'),
        ],
    ),
    retrieve=extend_schema(
        summary='Show Team',
        tags=['teams'],
        parameters=[build_expand_docs('members', 'invites', 'limit_tracks')],
    ),
    create=extend_schema(summary='Create Team', tags=['teams']),
    update=extend_schema(summary='Update Team', tags=['teams']),
    partial_update=extend_schema(summary='Update Team (Partial Update)', tags=['teams']),
    destroy=extend_schema(summary='Delete Team', tags=['teams']),
)
class TeamViewSet(PretalxViewSetMixin, viewsets.ModelViewSet):
    serializer_class = TeamSerializer
    queryset = Team.objects.none()
    endpoint = 'teams'
    search_fields = ('name',)

    def get_queryset(self):
        queryset = self.request.organizer.teams.all().select_related('organizer').order_by('pk')
        if fields := self.check_expanded_fields('members', 'limit_tracks', 'invites'):
            queryset = queryset.prefetch_related(*fields)
        return queryset

    def dispatch(self, request, *args, **kwargs):
        organizer = getattr(request, 'organizer', None)
        event_ids = tuple(organizer.events.values_list('pk', flat=True)) if organizer is not None else ()
        with scope(event=event_ids):
            return super().dispatch(request, *args, **kwargs)

    @transaction.atomic
    def perform_create(self, serializer):
        lock_team_organizer(self.request.organizer.pk)
        check_api_team_delegation(self.request, changes=serializer.validated_data)
        super().perform_create(serializer)

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        lock_team_organizer(request.organizer.pk)
        return super().update(request, *args, **kwargs)

    def perform_update(self, serializer):
        try:
            with transaction.atomic():
                check_api_team_delegation(self.request, team=serializer.instance, changes=serializer.validated_data)
                super().perform_update(serializer)
                check_access_permissions(self.request.organizer)
        except TeamPermissionError as e:
            raise exceptions.ValidationError(str(e))

    def perform_destroy(self, instance):
        try:
            with transaction.atomic():
                organizer = instance.organizer
                instance.logged_actions().delete()
                super().perform_destroy(instance)
                check_access_permissions(organizer)
        except TeamPermissionError as e:
            raise exceptions.ValidationError(str(e))

    @extend_schema(
        summary='Invite Member to Team',
        tags=['teams'],
        description='Creates a team invite, and sends an invite.',
        request=TeamInviteCreateSerializer,
    )
    @action(detail=True, methods=['post'])
    def invite(self, request, *args, **kwargs):
        team = self.get_object()
        input_serializer = TeamInviteCreateSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        email = input_serializer.validated_data['email']

        with transaction.atomic():
            try:
                invite = invite_to_team(
                    team,
                    email,
                    invited_by=request.user if request.user.is_authenticated else None,
                    actor=team_delegation_actor(request),
                    session_key=getattr(getattr(request, 'session', None), 'session_key', None),
                    locale=request.LANGUAGE_CODE,
                    log_kwargs={'user': request.user, 'auth': request.auth, 'orga': True},
                )
            except TeamInviteDelegationError as e:
                raise exceptions.PermissionDenied(str(e)) from e
            except TeamInviteError as e:
                raise exceptions.ValidationError(str(e))

        output_serializer = TeamInviteSerializer(invite, context=self.get_serializer_context())
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)

    @extend_schema(
        summary='Delete Team Invite',
        tags=['teams'],
        parameters=[OpenApiParameter('invite_id', OpenApiTypes.INT, OpenApiParameter.PATH)],
    )
    @action(detail=True, methods=['delete'], url_path='invites/(?P<invite_id>[^/.]+)')
    def delete_invite(self, request, invite_id, *args, **kwargs):
        team = self.get_object()
        invite = get_object_or_404(TeamInvite, pk=invite_id, team=team)
        email = invite.email
        invite.delete()
        team.log_action(
            'eventyay.team.invite.orga.retract',
            person=request.user,
            orga=True,
            data={'email': email},
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        summary='Remove Member from Team',
        tags=['teams'],
        request=TeamMemberRemoveSerializer,
        responses={
            204: OpenApiResponse(description='Member removed successfully.'),
            400: OpenApiResponse(description='Member cannot be removed as it may leave events inaccessible.'),
        },
    )
    @action(detail=True, methods=['post'], url_path='remove_member')
    def remove_member(self, request, *args, **kwargs):
        team = self.get_object()
        input_serializer = TeamMemberRemoveSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        user_code = input_serializer.validated_data['user_code']

        try:
            user_to_remove = User.objects.get(code=user_code)
        except User.DoesNotExist:
            raise exceptions.ValidationError('User with the specified code not found.')

        if not team.members.filter(pk=user_to_remove.pk).exists():
            raise exceptions.ValidationError('This user is not a member of this team.')

        try:
            with transaction.atomic():
                team.members.remove(user_to_remove)
                check_access_permissions(self.request.organizer)
                team.log_action(
                    'eventyay.team.remove_member',
                    person=request.user,
                    orga=True,
                    data={
                        'id': user_to_remove.id,
                        'name': user_to_remove.get_display_name(),
                        'email': user_to_remove.email,
                    },
                )
        except TeamPermissionError as e:
            raise exceptions.ValidationError(str(e))

        return Response(status=status.HTTP_204_NO_CONTENT)

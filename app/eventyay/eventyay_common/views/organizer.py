import logging
from urllib.parse import urljoin

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count
from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from django.views.generic import ListView

from eventyay.base.models import Organizer, Team
from eventyay.base.models.organizer import OrganizerBillingModel
from eventyay.base.settings import GlobalSettingsObject
from eventyay.control.forms.filter import OrganizerFilterForm
from eventyay.control.views import CreateView, PaginationMixin, UpdateView

from ...control.forms.organizer_forms import OrganizerForm, OrganizerUpdateForm
from ...control.permissions import OrganizerPermissionRequiredMixin

logger = logging.getLogger(__name__)


class OrganizerList(PaginationMixin, ListView):
    model = Organizer
    context_object_name = 'organizers'
    template_name = 'eventyay_common/organizers/index.html'

    def get_queryset(self):
        qs = Organizer.objects.all()
        if self.filter_form.is_valid():
            qs = self.filter_form.filter_qs(qs)
        if not self.request.user.has_active_staff_session(self.request.session.session_key):
            qs = qs.filter(pk__in=self.request.user.teams.values_list('organizer', flat=True))
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['filter_form'] = self.filter_form
        ctx['can_create_organizer'] = self._can_create_organizer(self.request.user)
        return ctx

    def _can_create_organizer(self, user):
        """
        Check if the user has permission to create an organizer.
        System admins can always create organizers.
        Other users can create organizers based on global settings.
        """
        # System admins can always create organizers
        if user.has_active_staff_session(self.request.session.session_key):
            return True

        # Get global settings
        gs = GlobalSettingsObject()
        allow_all_users = gs.settings.get('allow_all_users_create_organizer', None, as_type=bool)
        allow_payment_users = gs.settings.get('allow_payment_users_create_organizer', None, as_type=bool)

        # If neither option is explicitly set, default to allowing all users (permissive default)
        if allow_all_users is None and allow_payment_users is None:
            return True

        # If all users are allowed
        if allow_all_users:
            return True

        # If users with payment information are allowed
        if allow_payment_users:
            return self._user_has_payment_info(user)

        # By default, deny access if settings are explicitly set to False
        return False

    def _user_has_payment_info(self, user):
        """
        Check if the user has valid payment information on file.
        This is determined by checking if any of their organizers have a billing record with stripe_customer_id.
        """
        # Get all organizers where the user is a team member
        user_organizers = Organizer.objects.filter(
            teams__members=user
        ).distinct()

        # Check if any of these organizers have billing info with stripe_customer_id
        for organizer in user_organizers:
            billing = OrganizerBillingModel.objects.filter(
                organizer=organizer,
                stripe_customer_id__isnull=False
            ).exclude(stripe_customer_id='').first()
            if billing:
                return True

        return False

    @cached_property
    def filter_form(self):
        return OrganizerFilterForm(data=self.request.GET, request=self.request)


class OrganizerCreate(CreateView):
    model = Organizer
    form_class = OrganizerForm
    template_name = 'eventyay_common/organizers/create.html'
    context_object_name = 'organizer'

    def dispatch(self, request, *args, **kwargs):
        # Check if user has permission to create organizers
        if not self._can_create_organizer(request.user):
            messages.error(
                request,
                _('You do not have permission to create organizers. Please contact an administrator.')
            )
            raise PermissionDenied(_('You do not have permission to create organizers.'))
        return super().dispatch(request, *args, **kwargs)

    def _can_create_organizer(self, user):
        """
        Check if the user has permission to create an organizer.
        System admins can always create organizers.
        Other users can create organizers based on global settings.
        """
        # System admins can always create organizers
        if user.has_active_staff_session(self.request.session.session_key):
            return True

        # Get global settings
        gs = GlobalSettingsObject()
        allow_all_users = gs.settings.get('allow_all_users_create_organizer', None, as_type=bool)
        allow_payment_users = gs.settings.get('allow_payment_users_create_organizer', None, as_type=bool)

        # If neither option is explicitly set, default to allowing all users (permissive default)
        if allow_all_users is None and allow_payment_users is None:
            return True

        # If all users are allowed
        if allow_all_users:
            return True

        # If users with payment information are allowed
        if allow_payment_users:
            return self._user_has_payment_info(user)

        # By default, deny access if settings are explicitly set to False
        return False

    def _user_has_payment_info(self, user):
        """
        Check if the user has valid payment information on file.
        This is determined by checking if any of their organizers have a billing record with stripe_customer_id.
        """
        # Get all organizers where the user is a team member
        user_organizers = Organizer.objects.filter(
            teams__members=user
        ).distinct()

        # Check if any of these organizers have billing info with stripe_customer_id
        for organizer in user_organizers:
            billing = OrganizerBillingModel.objects.filter(
                organizer=organizer,
                stripe_customer_id__isnull=False
            ).exclude(stripe_customer_id='').first()
            if billing:
                return True

        return False

    @transaction.atomic
    def form_valid(self, form):
        messages.success(self.request, _('New organizer is created.'))
        response = super().form_valid(form)
        team = Team.objects.create(
            organizer=form.instance,
            name=_('Administrators'),
            all_events=True,
            can_create_events=True,
            can_change_teams=True,
            can_manage_gift_cards=True,
            can_change_organizer_settings=True,
            can_change_event_settings=True,
            can_change_items=True,
            can_view_orders=True,
            can_change_orders=True,
            can_view_vouchers=True,
            can_change_vouchers=True,
            can_change_submissions=True,
        )
        # Trigger webhook in talk to create organiser in talk component
        team.members.add(self.request.user)
        return response

    def get_success_url(self) -> str:
        return reverse('eventyay_common:organizers')

class OrganizerUpdate(UpdateView, OrganizerPermissionRequiredMixin):
    model = Organizer
    form_class = OrganizerUpdateForm
    template_name = 'eventyay_common/organizers/edit.html'
    permission = 'can_change_organizer_settings'
    context_object_name = 'organizer'

    @cached_property
    def object(self) -> Organizer:
        return self.request.organizer

    def get_object(self, queryset=None) -> Organizer:
        return self.object

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        org = self.object

        # Add Teams section only if user has team permissions
        user = self.request.user
        if user.has_organizer_permission(org, 'can_change_teams', request=self.request):
            ctx['teams'] = (
                org.teams.annotate(
                    memcount=Count('members', distinct=True),
                    eventcount=Count('limit_events', distinct=True),
                    invcount=Count('invites', distinct=True),
                )
                .all()
                .order_by('name')
            )
            ctx['can_manage_teams'] = True
        else:
            ctx['teams'] = []
            ctx['can_manage_teams'] = False

        return ctx
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        
        can_edit_general_info = self.request.user.has_organizer_permission(
            self.request.organizer,
            'can_change_organizer_settings',
            request=self.request
        )
        
        if not can_edit_general_info:
            form.fields['name'].disabled = True
            form.fields['slug'].disabled = True

        return form

    @transaction.atomic
    def form_valid(self, form):
        can_edit_general_info = self.request.user.has_organizer_permission(
            self.request.organizer,
            'can_change_organizer_settings',
            request=self.request
        )

        if not can_edit_general_info:
            form.cleaned_data['name'] = self.object.name
            form.cleaned_data['slug'] = self.object.slug

        messages.success(self.request, _('Your changes have been saved.'))
        response = super().form_valid(form)
        return response

    def get_success_url(self) -> str:
        return reverse('eventyay_common:organizers')

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models import Exists, OuterRef, Prefetch
from django.shortcuts import redirect
from django.utils.translation import gettext as _
from django.views.generic import DetailView, ListView

from eventyay.base.forms.organizer_request import OrganizerRequestRejectForm, OrganizerRequestReviewForm
from eventyay.base.models import OrganizerRequest, OrganizerRequestAnswer, User
from eventyay.base.services.organizer_requests import review_request
from eventyay.control.permissions import AdministratorPermissionRequiredMixin


class OrganizerRequestList(AdministratorPermissionRequiredMixin, ListView):
    template_name = 'pretixcontrol/admin/organizer_requests/list.html'
    context_object_name = 'applications'
    paginate_by = 25

    def get_queryset(self):
        return OrganizerRequest.objects.annotate(
            has_account=Exists(User.objects.filter(email__iexact=OuterRef('email')))
        )


class OrganizerRequestDetail(AdministratorPermissionRequiredMixin, DetailView):
    model = OrganizerRequest
    template_name = 'pretixcontrol/admin/organizer_requests/detail.html'
    context_object_name = 'application'
    queryset = OrganizerRequest.objects.select_related('reviewed_by', 'organizer').prefetch_related(
        Prefetch(
            'answers',
            queryset=OrganizerRequestAnswer.objects.select_related('question').order_by(
                'question__position', 'question_id'
            ),
        )
    )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.setdefault('form', OrganizerRequestReviewForm(instance=self.object))
        context.setdefault('reject_form', OrganizerRequestRejectForm())
        context['has_account'] = User.objects.filter(email__iexact=self.object.email).exists()
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        approve = request.POST.get('action') == 'approve'
        if request.POST.get('action') not in ('approve', 'reject'):
            return self.render_to_response(self.get_context_data(), status=400)
        form = (
            OrganizerRequestReviewForm(request.POST, instance=self.object)
            if approve
            else OrganizerRequestRejectForm(request.POST)
        )
        if form.is_valid():
            try:
                review_request(self.object.pk, request.user, approve=approve, **form.cleaned_data)
            except ValidationError as exc:
                form.add_error(None, exc)
            except IntegrityError:
                form.add_error(
                    None, _('The email or short form was just used by another request. Please reload and try again.')
                )
            else:
                messages.success(request, _('The request has been reviewed.'))
                return redirect('eventyay_admin:admin.organizer_requests.detail', pk=self.object.pk)
        context_key = 'form' if approve else 'reject_form'
        return self.render_to_response(self.get_context_data(**{context_key: form}))

from contextlib import contextmanager
from datetime import UTC, datetime

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.db.models import Exists, OuterRef, Prefetch, Q, QuerySet
from django.shortcuts import redirect
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.generic import DetailView, TemplateView

from eventyay.base.forms.organizer_request import OrganizerRequestRejectForm, OrganizerRequestReviewForm
from eventyay.base.models import OrganizerRequest, OrganizerRequestAnswer, User
from eventyay.base.services.organizer_requests import review_request
from eventyay.control.permissions import AdministratorPermissionRequiredMixin


REQUEST_PAGE_SIZE = 25


class RequestPage:
    def __init__(self, items: list[OrganizerRequest], *, has_previous: bool, has_next: bool):
        self.items = items
        self.has_previous = has_previous
        self.has_next = has_next

    def __iter__(self):
        return iter(self.items)

    @property
    def previous_cursor(self) -> str:
        if not self.items:
            return ''
        return request_cursor(self.items[0])

    @property
    def next_cursor(self) -> str:
        if not self.items:
            return ''
        return request_cursor(self.items[-1])


def request_cursor(application: OrganizerRequest) -> str:
    created = application.created.isoformat() if application.created else ''
    return f'{created}|{application.pk}'


def parse_cursor(value: str | None) -> tuple[datetime, int] | None:
    if not value or '|' not in value:
        return None
    created_text, pk_text = value.rsplit('|', 1)
    try:
        created = datetime.fromisoformat(created_text)
        pk = int(pk_text)
    except ValueError:
        return None
    if timezone.is_naive(created):
        created = timezone.make_aware(created, UTC)
    return created, pk


def older_than(created: datetime, pk: int) -> Q:
    return Q(created__lt=created) | Q(created=created, pk__lt=pk)


def newer_than(created: datetime, pk: int) -> Q:
    return Q(created__gt=created) | Q(created=created, pk__gt=pk)


def mark_existing_account(application: OrganizerRequest) -> None:
    if application.status == OrganizerRequest.Status.APPROVED:
        application.had_existing_account = not application.new_account
        return
    application.had_existing_account = bool(application.has_account)


def paginate_requests(
    queryset: QuerySet,
    *,
    before: str | None,
    after: str | None,
    mark_account: bool = False,
) -> RequestPage:
    ordered = queryset.order_by('-created', '-pk')
    before_cursor = parse_cursor(before)
    after_cursor = None if before_cursor else parse_cursor(after)
    if after_cursor:
        created, pk = after_cursor
        fetched = list(queryset.filter(newer_than(created, pk)).order_by('created', 'pk')[: REQUEST_PAGE_SIZE + 1])
        has_previous = len(fetched) > REQUEST_PAGE_SIZE
        items = list(reversed(fetched[:REQUEST_PAGE_SIZE]))
        has_next = ordered.filter(older_than(created, pk) | Q(created=created, pk=pk)).exists()
        if not items:
            fetched = list(ordered[: REQUEST_PAGE_SIZE + 1])
            has_previous = False
            has_next = len(fetched) > REQUEST_PAGE_SIZE
            items = fetched[:REQUEST_PAGE_SIZE]
    elif before_cursor:
        created, pk = before_cursor
        fetched = list(ordered.filter(older_than(created, pk))[: REQUEST_PAGE_SIZE + 1])
        has_next = len(fetched) > REQUEST_PAGE_SIZE
        items = fetched[:REQUEST_PAGE_SIZE]
        if items:
            has_previous = ordered.filter(newer_than(items[0].created, items[0].pk)).exists()
        else:
            tail = list(ordered.order_by('created', 'pk')[: REQUEST_PAGE_SIZE + 1])
            has_previous = len(tail) > REQUEST_PAGE_SIZE
            items = list(reversed(tail[:REQUEST_PAGE_SIZE]))
            has_next = False
    else:
        fetched = list(ordered[: REQUEST_PAGE_SIZE + 1])
        has_next = len(fetched) > REQUEST_PAGE_SIZE
        items = fetched[:REQUEST_PAGE_SIZE]
        has_previous = False
    if mark_account:
        for application in items:
            mark_existing_account(application)
    return RequestPage(items, has_previous=has_previous, has_next=has_next)


@contextmanager
def consistent_read():
    if connection.vendor == 'postgresql' and connection.get_autocommit():
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
            yield
        return
    yield


class OrganizerRequestList(AdministratorPermissionRequiredMixin, TemplateView):
    template_name = 'pretixcontrol/admin/organizer_requests/list.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        requests = OrganizerRequest.objects.annotate(
            has_account=Exists(User.objects.filter(email__iexact=OuterRef('email')))
        )
        with consistent_read():
            context['open_page'] = paginate_requests(
                requests.filter(status=OrganizerRequest.Status.PENDING),
                before=self.request.GET.get('open_before'),
                after=self.request.GET.get('open_after'),
            )
            context['resolved_page'] = paginate_requests(
                requests.filter(
                    status__in=(OrganizerRequest.Status.APPROVED, OrganizerRequest.Status.REJECTED)
                ).select_related('reviewed_by'),
                before=self.request.GET.get('resolved_before'),
                after=self.request.GET.get('resolved_after'),
                mark_account=True,
            )
        return context


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

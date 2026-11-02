import hashlib

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.http import Http404, HttpResponse, HttpResponseNotAllowed, JsonResponse
from django.urls import reverse_lazy
from django.utils.translation import gettext as _
from django.views.generic import FormView, TemplateView

from eventyay.base.forms.organizer_request import OrganizerRequestForm, validate_request_slug
from eventyay.base.models import OrganizerRequest
from eventyay.base.organizer_request_fields import organizer_request_enabled
from eventyay.base.services.organizer_requests import notify_submission
from eventyay.helpers.http import get_client_ip


ORGANIZER_REQUEST_RATE_LIMIT = 10
ORGANIZER_REQUEST_SLUG_RATE_LIMIT = 60
ORGANIZER_REQUEST_RATE_LIMIT_WINDOW = 15 * 60
ORGANIZER_REQUEST_SLUG_MAX_LENGTH = OrganizerRequest._meta.get_field('slug').max_length


def is_rate_limited(request, *, scope: str, limit: int) -> bool:
    client_ip = get_client_ip(request) or 'unknown'
    key = f'organizer_request:{scope}:' + hashlib.sha256(client_ip.encode()).hexdigest()
    if cache.add(key, 1, timeout=ORGANIZER_REQUEST_RATE_LIMIT_WINDOW):
        return False
    try:
        return cache.incr(key) > limit
    except ValueError:
        cache.add(key, 1, timeout=ORGANIZER_REQUEST_RATE_LIMIT_WINDOW)
        return False


def disabled_response() -> None:
    if not organizer_request_enabled():
        raise Http404


class OrganizerRequestCreate(FormView):
    form_class = OrganizerRequestForm
    template_name = 'eventyay_common/organizer_request/form.html'
    success_url = reverse_lazy('organizer_request.success')

    def get_form_kwargs(self):
        return {**super().get_form_kwargs(), 'request': self.request}

    def dispatch(self, request, *args, **kwargs):
        disabled_response()
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        return {**super().get_context_data(**kwargs), 'site_url': settings.SITE_URL.rstrip('/')}

    def post(self, request, *args, **kwargs):
        if is_rate_limited(request, scope='submit', limit=ORGANIZER_REQUEST_RATE_LIMIT):
            response = HttpResponse(_('Too many requests. Please try again in 15 minutes.'), status=429)
            response['Retry-After'] = str(ORGANIZER_REQUEST_RATE_LIMIT_WINDOW)
            return response
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        try:
            with transaction.atomic():
                application = form.save()
                form.save_answers(application)
                transaction.on_commit(lambda: notify_submission(application))
        except IntegrityError:
            collision = False
            for field in ('email', 'slug'):
                if OrganizerRequest.objects.filter(
                    **{f'{field}__iexact': form.cleaned_data[field]}, status='pending'
                ).exists():
                    form.add_error(field, _('There is already a pending request with this value.'))
                    collision = True
            if not collision:
                raise
            return self.form_invalid(form)
        return super().form_valid(form)


class OrganizerRequestSuccess(TemplateView):
    template_name = 'eventyay_common/organizer_request/success.html'

    def dispatch(self, request, *args, **kwargs):
        disabled_response()
        return super().dispatch(request, *args, **kwargs)


def slug_available(request):
    disabled_response()
    if request.method != 'GET':
        return HttpResponseNotAllowed(['GET'])
    if is_rate_limited(request, scope='slug', limit=ORGANIZER_REQUEST_SLUG_RATE_LIMIT):
        response = JsonResponse(
            {'available': False, 'message': _('Too many requests. Please try again in 15 minutes.')}, status=429
        )
        response['Retry-After'] = str(ORGANIZER_REQUEST_RATE_LIMIT_WINDOW)
        return response
    slug = request.GET.get('slug', '')
    if len(slug) > ORGANIZER_REQUEST_SLUG_MAX_LENGTH:
        return JsonResponse(
            {
                'available': False,
                'message': _('Use at most {max_length} characters.').format(
                    max_length=ORGANIZER_REQUEST_SLUG_MAX_LENGTH
                ),
            }
        )
    try:
        validate_request_slug(slug)
    except ValidationError as exc:
        return JsonResponse({'available': False, 'message': ' '.join(exc.messages)})
    return JsonResponse({'available': True, 'message': _('This short form is available.')})

import nh3
import json
from django import forms
from django.conf import settings
from django.contrib import messages
from django.http import Http404, HttpResponseRedirect, JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import FormView, ListView, TemplateView, UpdateView

from eventyay.base.models.page import Page
from eventyay.base.templatetags.rich_text import compile_markdown
from eventyay.control.forms.page import PageSettingsForm
from eventyay.control.permissions import AdministratorPermissionRequiredMixin
from eventyay.helpers.compat import CompatDeleteView


class PageList(AdministratorPermissionRequiredMixin, ListView):
    model = Page
    context_object_name = 'pages'
    paginate_by = 20
    template_name = 'pretixcontrol/admin/pages/index.html'


class PageCreate(AdministratorPermissionRequiredMixin, FormView):
    model = Page
    template_name = 'pretixcontrol/admin/pages/form.html'
    form_class = PageSettingsForm

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['locales'] = [(locale[0], locale[1]) for locale in settings.LANGUAGES]
        return ctx

    def get_success_url(self) -> str:
        return reverse(
            'eventyay_admin:admin.pages',
        )

    def form_valid(self, form):
        form.save()
        messages.success(self.request, _('Your changes have been saved.'))
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, _('Your changes have not been saved, see below for errors.'))
        return super().form_invalid(form)


class PageDetailMixin:
    def get_object(self, queryset=None) -> Page:
        try:
            return Page.objects.get(id=self.kwargs['id'])
        except Page.DoesNotExist:
            raise Http404(_('The requested page does not exist.'))

    def get_success_url(self) -> str:
        return reverse(
            'eventyay_admin:admin.pages',
        )


class PageEditForm(PageSettingsForm):
    slug = forms.CharField(label=_('URL form'), disabled=True)

    def clean_slug(self):
        return self.instance.slug


class PageUpdate(AdministratorPermissionRequiredMixin, PageDetailMixin, UpdateView):
    model = Page
    form_class = PageEditForm
    template_name = 'pretixcontrol/admin/pages/form.html'
    context_object_name = 'page'

    def get_success_url(self) -> str:
        return reverse(
            'eventyay_admin:admin.pages.edit',
            kwargs={
                'id': self.object.pk,
            },
        )

    def get_text_for_language(self, lng_code: str) -> str:
        if not self.object.text or not isinstance(self.object.text.data, dict):
            return ''
        return self.object.text.data.get(lng_code, '')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data()
        ctx['locales'] = []
        ctx['url'] = f'{settings.SITE_URL}/{settings.BASE_PATH}page/{self.object.slug}'

        for lng_code, lng_name in settings.LANGUAGES:
            ctx['locales'].append((lng_code, lng_name))
            ctx[f'text_{lng_code}'] = self.get_text_for_language(lng_code)
        return ctx

    def form_valid(self, form):
        messages.success(self.request, _('Your changes have been saved.'))
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, _('We could not save your changes. See below for details.'))
        return super().form_invalid(form)


class PageVisibilityToggle(AdministratorPermissionRequiredMixin, PageDetailMixin, View):
    _field_by_scope = {
        'startpage': 'link_on_website_start_page',
        'system': 'link_in_system',
    }

    def post(self, request, *args, **kwargs):
        is_json_request = (request.content_type or '').startswith('application/json')
        data = request.POST
        if not data:
            try:
                data = json.loads(request.body.decode('utf-8'))
            except (ValueError, AttributeError):
                data = {}

        scope = self.kwargs.get('scope')
        field_name = self._field_by_scope.get(scope)
        if not field_name:
            if is_json_request:
                return JsonResponse({'ok': False, 'error': _('Invalid field.')}, status=400)
            raise Http404(_('The requested page does not exist.'))

        page = self.get_object()
        value = data.get('value')
        if value is None:
            new_value = not getattr(page, field_name)
        else:
            new_value = str(value).lower() in {'true', '1', 'yes', 'on'}

        setattr(page, field_name, new_value)
        page.save(update_fields=[field_name])

        if is_json_request:
            return JsonResponse(
                {
                    'ok': True,
                    'startpage': page.link_on_website_start_page,
                    'system': page.link_in_system,
                }
            )

        next_url = request.POST.get('next', '')
        if next_url and url_has_allowed_host_and_scheme(
            next_url,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        ):
            return redirect(next_url)
        return redirect('eventyay_admin:admin.pages')


class PageDelete(AdministratorPermissionRequiredMixin, PageDetailMixin, CompatDeleteView):
    model = Page
    template_name = 'pretixcontrol/admin/pages/delete.html'
    context_object_name = 'page'

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.delete()
        messages.success(request, _('The selected page has been deleted.'))
        return HttpResponseRedirect(self.get_success_url())


class ShowPageView(TemplateView):
    template_name = 'pretixcontrol/admin/pages/show.html'

    def get_page(self):
        try:
            return Page.objects.get(slug=self.kwargs['slug'])
        except Page.DoesNotExist:
            raise Http404(_('The requested page does not exist.'))

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data()
        page = self.get_page()
        ctx['page'] = page
        ctx['show_link_in_header_for_all_pages'] = Page.objects.filter(link_in_system=True, link_in_header=True)
        ctx['show_link_in_footer_for_all_pages'] = Page.objects.filter(link_in_system=True, link_in_footer=True)

        attributes = {
            **nh3.ALLOWED_ATTRIBUTES,
            'a': nh3.ALLOWED_ATTRIBUTES['a'] | {'title', 'target'},
            'p': {'class'},
            'li': {'class'},
        }

        tags = nh3.ALLOWED_TAGS

        url_schemes = set(getattr(nh3, 'DEFAULT_URL_SCHEMES', nh3.ALLOWED_URL_SCHEMES)) | {'data'}

        ctx['content'] = nh3.clean(
            compile_markdown(str(page.text)),
            tags=tags,
            attributes=attributes,
            url_schemes=url_schemes,
        )
        return ctx

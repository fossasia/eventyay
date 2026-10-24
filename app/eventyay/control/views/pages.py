import json
from urllib.parse import urljoin

import nh3
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
from i18nfield.strings import LazyI18nString

from eventyay.base.models.page import (
    SYSTEM_PAGE_SLUGS,
    Page,
    get_visible_system_pages,
    is_content_empty,
)
from eventyay.base.settings import GlobalSettingsObject
from eventyay.common.permissions import is_admin_mode_active
from eventyay.control.forms.page import PageSettingsForm
from eventyay.control.forms.pages_admin import (
    ALL_PAGE_I18N_KEYS,
    DEFAULT_PAGE_LOCALE,
    DEFAULT_PAGE_SLUGS,
    PAGE_TITLES,
    DefaultPageContentForm,
    FooterContentForm,
    GlobalBannerContentForm,
    StartPageContentForm,
)
from eventyay.control.permissions import AdministratorPermissionRequiredMixin
from eventyay.eventyay_common.navigation import get_global_navigation
from eventyay.helpers.compat import CompatDeleteView


def build_pages_tabs(active):
    """Return the tab definitions for the consolidated admin *Pages* area.

    ``active`` is either a static tab key ("startpage", "footer", "banner",
    "additional") or a default-page slug (e.g. "terms").
    """
    tabs = [
        {'key': 'startpage', 'label': _('Start page'), 'url': reverse('eventyay_admin:admin.pages')},
        {'key': 'footer', 'label': _('Footer'), 'url': reverse('eventyay_admin:admin.pages.footer')},
    ]
    for slug in DEFAULT_PAGE_SLUGS:
        tabs.append(
            {
                'key': slug,
                'label': PAGE_TITLES[slug],
                'url': reverse('eventyay_admin:admin.pages.default', kwargs={'slug': slug}),
            }
        )
    tabs.append({'key': 'banner', 'label': _('Global banner'), 'url': reverse('eventyay_admin:admin.pages.banner')})
    tabs.append(
        {'key': 'additional', 'label': _('Additional pages'), 'url': reverse('eventyay_admin:admin.pages.additional')}
    )
    for tab in tabs:
        tab['active'] = tab['key'] == active
    return tabs


class PagesTabMixin:
    """Shared context (tab bar) for every view rendered inside the Pages area."""

    tab_key = None

    def get_active_tab(self):
        """Return the key of the active navigation tab."""
        return self.tab_key

    def get_context_data(self, **kwargs):
        """Inject page tab navigation definitions into template context."""
        ctx = super().get_context_data(**kwargs)
        ctx['page_tabs'] = build_pages_tabs(self.get_active_tab())
        return ctx


class PagesSettingsView(PagesTabMixin, AdministratorPermissionRequiredMixin, FormView):
    """Base FormView for the settings-backed Pages tabs."""

    def form_valid(self, form):
        """Save settings form changes and display a success message."""
        form.save()
        messages.success(self.request, _('Your changes have been saved.'))
        return super().form_valid(form)

    def form_invalid(self, form):
        """Display an error notification when form validation fails."""
        messages.error(self.request, _('Your changes have not been saved, see below for errors.'))
        return super().form_invalid(form)


class PagesStartPageView(PagesSettingsView):
    """Admin view for editing start page header, hero, and feature settings."""

    template_name = 'pretixcontrol/admin/pages/startpage.html'
    form_class = StartPageContentForm
    tab_key = 'startpage'

    def get_success_url(self):
        """Return redirect URL after saving start page settings."""
        return reverse('eventyay_admin:admin.pages')


class PagesFooterView(PagesSettingsView):
    """Admin view for editing global footer content and link settings."""

    template_name = 'pretixcontrol/admin/pages/footer.html'
    form_class = FooterContentForm
    tab_key = 'footer'

    def get_success_url(self):
        """Return redirect URL after saving footer settings."""
        return reverse('eventyay_admin:admin.pages.footer')


class PagesGlobalBannerView(PagesSettingsView):
    """Admin view for editing the global sitewide banner message."""

    template_name = 'pretixcontrol/admin/pages/banner.html'
    form_class = GlobalBannerContentForm
    tab_key = 'banner'

    def get_success_url(self):
        """Return redirect URL after saving global banner settings."""
        return reverse('eventyay_admin:admin.pages.banner')


class PagesDefaultPageView(PagesSettingsView):
    """Admin view for configuring built-in default pages (Terms, Privacy, Pricing, Support, Documentation)."""

    template_name = 'pretixcontrol/admin/pages/default_page.html'
    form_class = DefaultPageContentForm

    def dispatch(self, request, *args, **kwargs):
        """Validate default page slug and dispatch the request."""
        self.slug = kwargs.get('slug')
        if self.slug not in DEFAULT_PAGE_SLUGS:
            raise Http404(_('The requested page does not exist.'))
        return super().dispatch(request, *args, **kwargs)

    def get_active_tab(self):
        """Return current page slug as active tab key."""
        return self.slug

    def get_form_kwargs(self):
        """Pass the slug parameter into the form initialization kwargs."""
        kwargs = super().get_form_kwargs()
        kwargs['slug'] = self.slug
        return kwargs

    def get_context_data(self, **kwargs):
        """Populate template context with page metadata and preview URL."""
        ctx = super().get_context_data(**kwargs)
        ctx['slug'] = self.slug
        ctx['page_title'] = PAGE_TITLES.get(self.slug, self.slug)
        ctx['has_content'] = self.slug in ('terms', 'privacy', 'pricing', 'support')
        ctx['enabled_field'] = f'footer_link_{self.slug}_enabled'
        ctx['url_field'] = f'footer_link_{self.slug}_url'
        ctx['content_field'] = f'footer_page_{self.slug}_text'
        if self.slug == 'documentation':
            gs = GlobalSettingsObject().settings
            ctx['preview_url'] = gs.get('footer_link_documentation_url') or 'https://docs.eventyay.com'
        else:
            ctx['preview_url'] = f'/{self.slug}/'
        return ctx

    def get_success_url(self):
        """Return redirect URL after saving default page settings."""
        return reverse('eventyay_admin:admin.pages.default', kwargs={'slug': self.slug})


class PagesLocaleRemoveView(AdministratorPermissionRequiredMixin, View):
    """Remove a language from all page content and from page_locales globally."""

    def post(self, request, *args, **kwargs):
        """Remove the selected locale from page settings and redirect back safely."""
        locale = (request.POST.get('locale') or '').strip().lower()
        valid_codes = {code for code, _name in settings.LANGUAGES}
        if not locale or locale not in valid_codes:
            messages.error(request, _('Invalid language code.'))
            return redirect(reverse('eventyay_admin:admin.pages'))

        gs = GlobalSettingsObject().settings

        raw = gs.get('page_locales')
        if isinstance(raw, str):
            try:
                locales = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                locales = [DEFAULT_PAGE_LOCALE]
        elif isinstance(raw, (list, tuple)):
            locales = list(raw)
        else:
            locales = [DEFAULT_PAGE_LOCALE]

        if locale not in locales:
            messages.warning(request, _('That language is not currently active.'))
            return redirect(reverse('eventyay_admin:admin.pages'))

        if len(locales) <= 1:
            messages.error(request, _('You must keep at least one language.'))
            return redirect(reverse('eventyay_admin:admin.pages'))

        # Strip the locale from every i18n content key across all tabs.
        for key in ALL_PAGE_I18N_KEYS:
            raw_val = gs.get(key)
            if raw_val is None:
                continue
            if isinstance(raw_val, LazyI18nString):
                data = raw_val.data
            elif isinstance(raw_val, str):
                try:
                    data = json.loads(raw_val)
                except (json.JSONDecodeError, TypeError):
                    data = raw_val
            else:
                data = raw_val
            if isinstance(data, dict) and locale in data:
                del data[locale]
                gs.set(key, LazyI18nString(data))

        locales = [c for c in locales if c != locale]
        gs.set('page_locales', json.dumps(locales))

        messages.success(request, _('Language removed from all page content.'))

        referer = request.POST.get('next') or request.META.get('HTTP_REFERER') or ''
        if referer and url_has_allowed_host_and_scheme(
            referer, allowed_hosts={request.get_host()}, require_https=request.is_secure()
        ):
            return redirect(referer)
        return redirect(reverse('eventyay_admin:admin.pages'))


class PageList(PagesTabMixin, AdministratorPermissionRequiredMixin, ListView):
    """List custom database content pages."""

    model = Page
    context_object_name = 'pages'
    paginate_by = 20
    template_name = 'pretixcontrol/admin/pages/index.html'
    tab_key = 'additional'


class PageCreate(PagesTabMixin, AdministratorPermissionRequiredMixin, FormView):
    """Create a new custom database page."""

    model = Page
    template_name = 'pretixcontrol/admin/pages/form.html'
    form_class = PageSettingsForm
    tab_key = 'additional'

    def get_context_data(self, **kwargs):
        """Provide available languages to the page creation form context."""
        ctx = super().get_context_data(**kwargs)
        ctx['locales'] = [(locale[0], locale[1]) for locale in settings.LANGUAGES]
        return ctx

    def get_success_url(self) -> str:
        """Return redirect URL after creating a custom page."""
        return reverse('eventyay_admin:admin.pages.additional')

    def form_valid(self, form):
        """Save the new page and display success message."""
        form.save()
        messages.success(self.request, _('Your changes have been saved.'))
        return super().form_valid(form)

    def form_invalid(self, form):
        """Display error message on invalid page creation form submission."""
        messages.error(self.request, _('Your changes have not been saved, see below for errors.'))
        return super().form_invalid(form)


class PageDetailMixin:
    """Helper mixin to fetch a Page by its primary key."""

    def get_object(self, queryset=None) -> Page:
        """Fetch Page by id parameter or raise Http404."""
        try:
            return Page.objects.get(id=self.kwargs['id'])
        except Page.DoesNotExist:
            raise Http404(_('The requested page does not exist.'))

    def get_success_url(self) -> str:
        """Return redirect URL to additional pages list."""
        return reverse('eventyay_admin:admin.pages.additional')


class PageEditForm(PageSettingsForm):
    """Form for editing an existing custom page with disabled slug field."""

    slug = forms.CharField(label=_('URL form'), disabled=True)

    def clean_slug(self):
        """Preserve existing slug on edit."""
        return self.instance.slug


class PageUpdate(PagesTabMixin, AdministratorPermissionRequiredMixin, PageDetailMixin, UpdateView):
    """Edit an existing custom database page."""

    model = Page
    form_class = PageEditForm
    template_name = 'pretixcontrol/admin/pages/form.html'
    context_object_name = 'page'
    tab_key = 'additional'

    def get_success_url(self) -> str:
        """Return redirect URL after updating page."""
        return reverse(
            'eventyay_admin:admin.pages.edit',
            kwargs={'id': self.object.pk},
        )

    def get_text_for_language(self, lng_code: str) -> str:
        """Extract page text for the specified language code."""
        if not self.object.text or not isinstance(self.object.text.data, dict):
            return ''
        return self.object.text.data.get(lng_code, '')

    def get_context_data(self, **kwargs):
        """Inject per-language text values and public page URL into context."""
        ctx = super().get_context_data()
        ctx['locales'] = []
        ctx['url'] = urljoin(settings.SITE_URL.rstrip('/') + '/', f'{settings.BASE_PATH}page/{self.object.slug}')

        for lng_code, lng_name in settings.LANGUAGES:
            ctx['locales'].append((lng_code, lng_name))
            ctx[f'text_{lng_code}'] = self.get_text_for_language(lng_code)
        return ctx

    def form_valid(self, form):
        """Save page modifications and display success message."""
        messages.success(self.request, _('Your changes have been saved.'))
        return super().form_valid(form)

    def form_invalid(self, form):
        """Display error message on invalid page update."""
        messages.error(self.request, _('We could not save your changes. See below for details.'))
        return super().form_invalid(form)


class PageVisibilityToggle(AdministratorPermissionRequiredMixin, PageDetailMixin, View):
    """Toggle page visibility settings (startpage or system scope) via AJAX or standard POST."""

    _field_by_scope = {
        'startpage': 'link_on_website_start_page',
        'system': 'link_in_system',
    }

    def post(self, request, *args, **kwargs):
        """Toggle page boolean field and return JSON or redirect response."""
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
        return redirect('eventyay_admin:admin.pages.additional')


class PageDelete(AdministratorPermissionRequiredMixin, PageDetailMixin, CompatDeleteView):
    """Delete a custom database page."""

    model = Page
    template_name = 'pretixcontrol/admin/pages/delete.html'
    context_object_name = 'page'

    def delete(self, request, *args, **kwargs):
        """Delete page object and redirect with success message."""
        self.object = self.get_object()
        self.object.delete()
        messages.success(request, _('The selected page has been deleted.'))
        return HttpResponseRedirect(self.get_success_url())


class ShowPageView(TemplateView):
    """Display a rendered content page or system default page."""

    template_name = 'pretixcontrol/admin/pages/show.html'
    system_page_slugs = SYSTEM_PAGE_SLUGS

    def get_slug(self):
        """Return page slug from URL kwargs."""
        return self.kwargs.get('slug')

    def get_page(self):
        """Resolve Page instance from DB or fallback to global settings text for system pages."""
        raw_slug = self.get_slug()
        if not raw_slug:
            raise Http404(_('The requested page does not exist.'))
        slug = str(raw_slug).strip().lower()
        gs = GlobalSettingsObject().settings

        def _get_db_page(lookup_slug):
            page = Page.objects.filter(slug=lookup_slug).first()
            if not page:
                page = Page.objects.filter(slug__iexact=lookup_slug).first()
            if page and is_content_empty(page.text):
                has_content = (
                    Page.objects.filter(slug=lookup_slug)
                    .exclude(text__isnull=True)
                    .exclude(text='')
                    .exclude(text='{}')
                    .first()
                )
                if has_content and not is_content_empty(has_content.text):
                    return has_content
                has_content_iexact = (
                    Page.objects.filter(slug__iexact=lookup_slug)
                    .exclude(text__isnull=True)
                    .exclude(text='')
                    .exclude(text='{}')
                    .first()
                )
                if has_content_iexact and not is_content_empty(has_content_iexact.text):
                    return has_content_iexact
            return page

        if slug in self.system_page_slugs:
            enabled_key = f'footer_link_{slug}_enabled'
            if not gs.get(enabled_key, as_type=bool, default=True):
                raise Http404(_('The requested page does not exist.'))

            custom_text = gs.get(f'footer_page_{slug}_text', as_type=LazyI18nString)
            if not is_content_empty(custom_text):
                title_map = {
                    'terms': _('Terms of Service'),
                    'privacy': _('Privacy Policy'),
                    'support': _('Support & Help'),
                }
                title = title_map.get(slug, slug.capitalize())
                return Page(
                    title=title,
                    slug=slug,
                    text=custom_text,
                )

            page = _get_db_page(slug)
            if page and not is_content_empty(page.text):
                return page

            raise Http404(_('The requested page does not exist.'))

        page = _get_db_page(slug)
        if page:
            return page
        raise Http404(_('The requested page does not exist.'))

    def get_context_data(self, **kwargs):
        """Prepare context with sanitized page content and navigation menus."""
        ctx = super().get_context_data()
        page = self.get_page()
        ctx['page'] = page
        ctx['staff_session'] = is_admin_mode_active(self.request)
        ctx['nav_items'] = get_global_navigation(self.request) if self.request.user.is_authenticated else []
        ctx['show_link_in_header_for_all_pages'] = get_visible_system_pages('link_in_header', request=self.request)
        ctx['show_link_in_footer_for_all_pages'] = get_visible_system_pages('link_in_footer', request=self.request)

        attributes = {
            **nh3.ALLOWED_ATTRIBUTES,
            'a': nh3.ALLOWED_ATTRIBUTES['a'] | {'title', 'target'},
            'p': {'class'},
            'li': {'class'},
        }

        tags = nh3.ALLOWED_TAGS

        url_schemes = set(getattr(nh3, 'DEFAULT_URL_SCHEMES', nh3.ALLOWED_URL_SCHEMES)) | {'data'}

        ctx['content'] = nh3.clean(
            str(page.text),
            tags=tags,
            attributes=attributes,
            url_schemes=url_schemes,
        )
        return ctx


class SystemPageView(ShowPageView):
    """Render system pages (terms, privacy, pricing, support) from DB or with default content if enabled."""

    slug = None

    def get_slug(self):
        """Return configured slug attribute or URL kwargs slug."""
        return self.slug or self.kwargs.get('slug')

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.http import HttpResponse, Http404
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.utils.html import format_html
from django.utils.module_loading import import_string
from django.views.generic import TemplateView, UpdateView

from collections import defaultdict

from .models import UserKey, DisabledFallback, KeyTypes, DOMAIN_KEYS
from .common import render, method_url, active_factors, has_multifactor, disabled_fallbacks
from .app_settings import mf_settings
from .decorators import multifactor_protected
from .mixins import RequireMultiAuthMixin, PreferMultiAuthMixin, MultiFactorMixin


class List(LoginRequiredMixin, RequireMultiAuthMixin, TemplateView):
    template_name = "multifactor/home.html"

    def get_context_data(self, **kwargs):
        can_edit = not self.has_multifactor or bool(self.active_factors)

        if not can_edit:
            messages.warning(self.request, format_html(
                'You will not be able to change these settings or add new '
                'factors until until you <a href="{}" class="alert-link">authenticate</a> with '
                'one of your existing secondary factors.',
                reverse('multifactor:authenticate')
            ))

        disabled = disabled_fallbacks(self.request)
        available_fallbacks = [
            (k, k not in disabled, v[0](self.request.user))
            for k, v in mf_settings['FALLBACKS'].items()
            if v[0](self.request.user)
        ]

        return {
            **super().get_context_data(**kwargs),
            "factors": self.factors,
            'authed_kids': [k[1] for k in self.active_factors],
            "can_edit": can_edit,
            'available_fallbacks': available_fallbacks,
        }

    def get(self, request, *args, **kwargs):
        # catch people who have ended up here from a auth request (authing or adding)
        if 'multifactor-next' in request.session:
            return redirect(request.session.pop('multifactor-next', 'multifactor:home'))

        # if 'action' in kwargs:
        #     raise Http404()
        return super().get(request, *args, **kwargs)

    def post(self, request, action, ident, *args, **kwargs):
        """ Wire through actions to action_ functions. """
        if hasattr(self, f"action_{action}"):
            getattr(self, f"action_{action}")(request, ident)
            return redirect('multifactor:home')
        raise Http404('Action not found')

    def action_toggle_factor(self, request, ident):
        try:
            factor = self.factors.get(pk=ident)
            factor.enabled = not factor.enabled
            factor.save()
            messages.info(request, f'{factor.get_key_type_display()} has been {"enabled" if factor.enabled else "disabled"}.')

        except UserKey.DoesNotExist:
            messages.error(request, f'{factor.get_key_type_display()} not found.')

    def action_delete_factor(self, request, ident):
        try:
            factor = self.factors.get(pk=ident)
            factor.delete()
            messages.info(request, f'{factor.get_key_type_display()} has been deleted.')

        except UserKey.DoesNotExist:
            messages.error(request, f"Couldn't find that factor.")


    def action_toggle_fallback(self, request, ident):
        if not (ident and ident in mf_settings['FALLBACKS']):
            return messages.error('Invalid fallback.')

        n, _ = DisabledFallback.objects.filter(user=request.user, fallback=ident).delete()
        if n:  # managed to delete something
            return messages.info(request, f"{ident} fallback factor has been re-enabled.")

        messages.info(request, f"{ident} fallback factor has been disabled.")
        DisabledFallback(user=request.user, fallback=ident).save()


class Add(LoginRequiredMixin, PreferMultiAuthMixin, TemplateView):
    template_name = 'multifactor/add.html'

    def get_context_data(self, **kwargs):
        return {
            **super().get_context_data(**kwargs),
            "methods": [
                (f"multifactor:{value.lower()}_start", label)
                for value, label in KeyTypes.choices
            ],
        }


class Rename(LoginRequiredMixin, RequireMultiAuthMixin, UpdateView):
    model = UserKey
    fields = ['name']
    success_url = reverse_lazy('multifactor:home')

    def get_queryset(self):
        return super().get_queryset().filter(user=self.request.user)


class Authenticate(LoginRequiredMixin, MultiFactorMixin, TemplateView):
    template_name = "multifactor/authenticate.html"

    def get(self, request, *args, **kwargs):
        self.available_methods = defaultdict(list)
        other_domains = set()

        for factor in self.factors:
            if factor.key_type in DOMAIN_KEYS:
                domain = factor.properties.get('domain', '')
                if not domain:
                    continue
                if domain != self.request.get_host().split(":")[0]:
                    other_domains.add(domain)
                    continue
            self.available_methods[factor.key_type].append(factor)

        if not other_domains and not self.available_methods:
            return redirect('multifactor:add')

        disabled_fbs = disabled_fallbacks(self.request)
        self.available_fallbacks = [
            k for k, v in mf_settings['FALLBACKS'].items()
            if k not in disabled_fbs and v[0](self.request.user)
        ]

        if len(self.available_methods) == 1 and not self.available_fallbacks:
            # if there's only one type of factor available
            # and no chance of a fallback, let's redirect them.
            return redirect(method_url(list(self.available_methods)[0]))

        if other_domains:
            domains = format_html(', '.join(['<a href="https://{0}{1}">{0}</a>'.format(d, self.request.path) for d in other_domains]))
            messages.info(self.request, format_html("You also have active domain-locked factors available on: {}", domains))

        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        method_names = dict(KeyTypes.choices)

        # build up a reminder string as one of the following:
        #  - 2 available
        #  - Car keys or usb stick
        #  - Key fob or 2 others
        factor_string = {}
        for method, factors in self.available_methods.items():
            named_factors = [f.name for f in factors if f.name]

            if not named_factors:
                factor_string[method] = f'{len(factors)} available'

            else:
                anon = len(factors) - len(named_factors)
                # print(factors, anon)
                if anon:
                    factor_string[method] = ', '.join(named_factors) + f' or {len(factors)} other{"" if anon == 1 else "s"}'
                elif len(factors) > 1:
                    factor_string[method] = ', '.join(named_factors[:1]) + ' or ' + named_factors[-1]
                else:
                    factor_string[method] = named_factors[0]

        return {
            **super().get_context_data(**kwargs),
            'methods': [
                (method_url(method), method_names[method], factor_string[method])
                for method in self.available_methods
            ],
            'fallbacks': self.available_fallbacks,
        }


class Help(TemplateView):
    template_name = 'multifactor/help.html'

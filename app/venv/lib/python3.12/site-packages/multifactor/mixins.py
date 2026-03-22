from django.shortcuts import redirect

from .models import UserKey
from .common import active_factors, is_bypassed


class MultiFactorMixin:
    """Verify that the current user is multifactor-authenticated or has no factors yet."""

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)

        if not request.user.is_authenticated:
            return

        self.active_factors = active_factors(request)
        self.factors = UserKey.objects.filter(user=request.user)
        self.has_multifactor = self.factors.filter(enabled=True).exists()
        self.bypass = is_bypassed(request)


class RequireMultiAuthMixin(MultiFactorMixin):
    """Require Multifactor, force user to add factors if none on account."""

    def dispatch(self, request, *args, **kwargs):
        if not self.active_factors and not self.bypass:
            request.session['multifactor-next'] = request.get_full_path()
            if self.has_multifactor:
                return redirect('multifactor:authenticate')

            return redirect('multifactor:add')

        return super().dispatch(request, *args, **kwargs)


class PreferMultiAuthMixin(MultiFactorMixin):
    """Use Multifactor if user has active factors."""

    def dispatch(self, request, *args, **kwargs):
        if not self.active_factors and not self.bypass and self.has_multifactor:
            request.session['multifactor-next'] = request.get_full_path()
            return redirect('multifactor:authenticate')

        return super().dispatch(request, *args, **kwargs)

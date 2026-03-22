import django
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html

import functools
import time
import inspect

from .common import method_url, active_factors, has_multifactor, is_bypassed


__all__ = ['multifactor_protected']


def multifactor_protected(factors=0, user_filter=None, max_age=0, advertise=False):
    """
    Protect a view with multifactor authentication.

    Parameters
    ----------
    factors : int, function
        Number of separate factors that must be currently activated.
        You can also pass in a function accepting the request to return this number.
    user_filter : None | dict
        User-class.objects.filter dictionary to try to match current user.
    max_age : int
        Number of seconds since last authentication this view requires.
        Zero means infinite (or until it expires)
    advertise : bool
        Advertise to the user that they can optionally add keys for factors=0 views.
    """
    def _func_wrapper(view_func, *args, **kwargs):
        @functools.wraps(view_func)
        def _wrapped_view_func(request, *args, **kwargs):
            def baulk():
                return view_func(request, *args, **kwargs)

            def force_authenticate():
                if django.VERSION < (4, 0) and request.is_ajax():
                    raise PermissionDenied('Multifactor authentication required')
                request.session['multifactor-next'] = request.get_full_path()
                return redirect('multifactor:authenticate')

            if not request.user.is_authenticated:
                return baulk()
            
            if is_bypassed(request):
                return baulk()

            if user_filter is not None:
                # we're filtering for specific users, check that the current user fits that
                if not get_user_model().objects.filter(pk=request.user.pk, **user_filter).exists():
                    return baulk()

            active = active_factors(request)

            if has_multifactor(request):
                if not active:
                    # has keys but isn't using them, tell them to authenticate
                    return force_authenticate()

                elif max_age and active[0][3] + max_age < timezone.now().timestamp():
                    # has authenticated but not recently enough for this view
                    messages.warning(
                        request,
                        f'This page requires secondary authentication every {max_age} seconds. '
                        'Please re-authenticate.'
                    )
                    return force_authenticate()

            required_factors = factors
            if inspect.isfunction(factors):
                required_factors = factors(request)

            if required_factors > len(active):
                # view needs more active factors than provided
                messages.warning(
                    request,
                    f'This page requires {required_factors} active security '
                    f'factor{"" if required_factors == 1 else "s"}.'
                )
                return force_authenticate()

            if not active and advertise and 'multifactor-advertised' not in request.session:
                # tell them that they can add keys but it's entirely optional
                messages.info(request, format_html(
                    'Make your account more secure by <a href="{}" class="alert-link">adding a second security factor</a> '
                    'such as a USB Security Token, or an Authenticator App.',
                    reverse('multifactor:home')
                ))
                request.session['multifactor-advertised'] = True

            return baulk()
        return _wrapped_view_func
    return _func_wrapper

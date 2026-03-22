import functools

from asgiref.sync import iscoroutinefunction, markcoroutinefunction

from django.utils.functional import SimpleLazyObject

from django_otp import DEVICE_ID_SESSION_KEY
from django_otp.models import Device


def is_verified(user):
    return user.otp_device is not None


class OTPMiddleware:
    """
    This must be installed after
    :class:`~django.contrib.auth.middleware.AuthenticationMiddleware` and
    performs an analogous function. Just as AuthenticationMiddleware populates
    ``request.user`` based on session data, OTPMiddleware populates
    ``request.user.otp_device`` to the :class:`~django_otp.models.Device`
    object that has verified the user, or ``None`` if the user has not been
    verified.  As a convenience, this also installs ``user.is_verified()``,
    which returns ``True`` if ``user.otp_device`` is not ``None``.

    This middleware is async capable. It wraps ``request.auser()`` similarly
    to ``request.user`` as described above.
    """

    sync_capable = True
    async_capable = True

    def __init__(self, get_response):
        self.get_response = get_response
        self._is_async = iscoroutinefunction(get_response)
        if self._is_async:
            markcoroutinefunction(self)

    def __call__(self, request):
        if self._is_async:
            return self.__acall__(request)

        self._install_lazy_accessors(request)
        return self.get_response(request)

    async def __acall__(self, request):
        self._install_lazy_accessors(request)
        return await self.get_response(request)

    def _install_lazy_accessors(self, request):
        user = getattr(request, "user", None)
        if user is not None:
            request.user = SimpleLazyObject(
                functools.partial(self._verify_user_sync, request, user)
            )

        auser = getattr(request, "auser", None)
        if auser is not None:
            request.auser = functools.partial(
                self._verify_user_async_via_auser, request, auser
            )

    @staticmethod
    def _init_user_fields(user):
        user.otp_device = None
        user.is_verified = functools.partial(is_verified, user)

    @staticmethod
    def _normalize_persistent_id(persistent_id: str) -> str:
        # Convert legacy persistent_id values (these used to be full import
        # paths). This won't work for apps with models in sub-modules, but that
        # should be pretty rare. And the worst that happens is the user has to
        # log in again.
        if persistent_id.count(".") > 1:
            parts = persistent_id.split(".")
            return ".".join((parts[-3], parts[-1]))
        return persistent_id

    @staticmethod
    def _finalize_device(request, user, device):
        """
        Enforce device-user binding and keep session state consistent.
        """
        if (device is not None) and (device.user_id != user.pk):
            device = None

        if (device is None) and (DEVICE_ID_SESSION_KEY in request.session):
            del request.session[DEVICE_ID_SESSION_KEY]

        return device

    def _verify_user_sync(self, request, user):
        self._init_user_fields(user)

        if user.is_authenticated:
            persistent_id = request.session.get(DEVICE_ID_SESSION_KEY)
            device = (
                self._device_from_persistent_id(persistent_id)
                if persistent_id
                else None
            )
            user.otp_device = self._finalize_device(request, user, device)

        return user

    def _device_from_persistent_id(self, persistent_id: str):
        persistent_id = self._normalize_persistent_id(persistent_id)
        return Device.from_persistent_id(persistent_id)

    async def _verify_user_async_via_auser(self, request, auser):
        user = await auser()
        self._init_user_fields(user)

        if user.is_authenticated:
            persistent_id = request.session.get(DEVICE_ID_SESSION_KEY)
            device = (
                await self._adevice_from_persistent_id(persistent_id)
                if persistent_id
                else None
            )
            user.otp_device = self._finalize_device(request, user, device)

        return user

    async def _adevice_from_persistent_id(self, persistent_id: str):
        persistent_id = self._normalize_persistent_id(persistent_id)
        return await Device.afrom_persistent_id(persistent_id)

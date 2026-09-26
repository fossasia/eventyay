import logging
from io import BytesIO
from pathlib import Path

from asgiref.sync import async_to_sync

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.base import ContentFile
from django.http import JsonResponse
from django.middleware.csrf import CsrfViewMiddleware
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.utils.functional import cached_property
from django.utils.timezone import now
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from PIL import Image
from rest_framework.authentication import get_authorization_header

from eventyay.base.models import Event
from eventyay.base.operational_logging import OUTCOME_FAILURE, is_safe_identifier, log_event
from eventyay.common.image import (
    IMAGE_EXTENSIONS,
    REWRITABLE_ORIGINAL_EXTENSIONS,
    encode_optimized,
)
from eventyay.consts import SizeKey
from eventyay.core.permissions import Permission
from eventyay.base.services.user import AuthError, login
from eventyay.base.services.event import notify_schedule_change
from eventyay.base.models.storage_model import StoredFile
from eventyay.storage.schedule_to_json import convert

logger = logging.getLogger(__name__)


class CSRFCheck(CsrfViewMiddleware):
    """CSRF middleware that returns the failure reason instead of an HTML response."""

    def _reject(self, request, reason):
        return reason


def enforce_csrf(request):
    """Require a valid CSRF token for session-authenticated uploads."""

    def dummy_get_response(request):  # pragma: no cover
        return None

    check = CSRFCheck(dummy_get_response)
    check.process_request(request)
    reason = check.process_view(request, None, (), {})
    if reason:
        raise PermissionDenied("CSRF verification failed.")


class UploadMixin:
    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    @cached_property
    def event(self):
        event_id = self.kwargs.get("event_id", None)
        return get_object_or_404(Event, id=event_id)

    @cached_property
    def user(self):
        # Upload is allowed if the user has update or chat rights in any room
        auth = get_authorization_header(self.request).decode().split()
        res = None

        if len(auth) == 2:
            if auth[0].lower() == "bearer":
                token = self.event.decode_token(auth[1])
                if token:
                    try:
                        res = login(event=self.event, token=token)
                    except AuthError:
                        pass
            elif auth[0].lower() == "client":
                try:
                    res = login(event=self.event, client_id=auth[1])
                except AuthError:
                    pass

        # Fallback to session authentication (CSRF required; token auth stays exempt)
        if not auth and not res and getattr(self.request, "user", None) and self.request.user.is_authenticated:
            enforce_csrf(self.request)
            try:
                res = login(event=self.event, platform_user=self.request.user)
            except AuthError:
                pass

        if not res:
            raise PermissionDenied()

        if any(p.value in res.event_config["permissions"] for p in self.permissions):
            return res.user
        for room in res.event_config["rooms"]:
            if any(p.value in room["permissions"] for p in self.permissions):
                return res.user
        raise PermissionDenied()


def unmodified_image(data, image):
    """Build the upload tuple for an image that is stored without recompression."""
    if hasattr(data, "seek"):
        data.seek(0)
    # The suffix has to describe the payload, because media servers derive the content
    # type of a stored file from its path rather than from StoredFile.type.
    extension = ".jpg" if image.format == "JPEG" else f".{image.format.lower()}"
    data.name = str(Path(data.name).with_suffix(extension))
    return Image.MIME.get(image.format), data, data.size


def upload_rejected(event, error, status=400):
    log_event(
        'video',
        'upload',
        OUTCOME_FAILURE,
        error_code=error if is_safe_identifier(error) else 'upload_error',
        event_id=getattr(event, 'pk', None),
    )
    return JsonResponse({"error": error}, status=status)


class UploadView(UploadMixin, View):
    permissions = {
        Permission.EVENT_VIEW,
        Permission.EVENT_UPDATE,
        Permission.ROOM_UPDATE,
        Permission.ROOM_CHAT_SEND,
    }
    ext_whitelist = (
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".pdf",
        ".svg",
        ".mp4",
        ".webm",
        ".mp3",
    )
    pillow_formats = (
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
    )
    max_size = settings.MAX_SIZE_CONFIG[SizeKey.UPLOAD_SIZE_OTHER]

    def post(self, request, *args, **kwargs):
        if not self.user:
            return  # triggers error already

        if "file" not in request.FILES:
            return upload_rejected(self.event, "file.missing")

        if not any(
            request.FILES["file"].name.lower().endswith(e) for e in self.ext_whitelist
        ):
            return upload_rejected(self.event, "file.type")

        if any(
            request.FILES["file"].name.lower().endswith(e) for e in self.pillow_formats
        ):
            try:
                content_type, file, size = self.validate_image(request.FILES["file"])
            except ValidationError:
                return upload_rejected(self.event, "file.picture.invalid")
        else:
            file = request.FILES["file"]
            content_type = request.FILES["file"].content_type
            size = request.FILES["file"].size

        if size > self.max_size:
            return upload_rejected(self.event, "file.size")

        sf = StoredFile.objects.create(
            event=self.event,
            date=now(),
            filename=file.name,
            type=content_type,
            file=file,
            public=True,
            user=self.user,
        )
        return JsonResponse({"url": sf.file.url}, status=201)

    def validate_image(self, data):
        # partially vendored from django.forms.fields.ImageField
        # We need to get a file object for Pillow. We might have a path or we might
        # have to read the data into memory.
        if hasattr(data, "temporary_file_path"):
            file = data.temporary_file_path()
        else:
            if hasattr(data, "read"):
                file = BytesIO(data.read())
            else:
                file = BytesIO(data["content"])

        try:
            # load() could spot a truncated JPEG, but it loads the entire
            # image in memory, which is a DoS vector. See #3848 and #18520.
            image = Image.open(file)
            # verify() must be called immediately after the constructor.
            image.verify()
        except Exception:
            # Pillow doesn't recognize it as an image.
            raise ValidationError("invalid image")

        if hasattr(file, "seek"):
            file.seek(0)

        image = Image.open(file)
        original_ext = Path(data.name).suffix.lower()
        if original_ext == ".jpeg":
            original_ext = ".jpg"

        # Animated images lose their frames when re-encoded, so they are stored as they are.
        if getattr(image, "is_animated", False) or original_ext not in REWRITABLE_ORIGINAL_EXTENSIONS:
            return unmodified_image(data, image)

        max_dimensions = self.requested_dimensions() or (
            settings.IMAGE_DEFAULT_MAX_WIDTH,
            settings.IMAGE_DEFAULT_MAX_HEIGHT,
        )
        optimized, optimized_ext = encode_optimized(
            image,
            original_ext,
            max_dimensions=max_dimensions,
            keep_format=True,
        )
        # Recompressing a lossless image can make it bigger, but an image that had to be
        # scaled down is always stored recompressed, and so is JPEG, whose EXIF metadata
        # must never reach storage.
        fits_dimensions = image.width <= max_dimensions[0] and image.height <= max_dimensions[1]
        if fits_dimensions and optimized_ext == original_ext != ".jpg" and len(optimized) >= data.size:
            return unmodified_image(data, image)

        return (
            IMAGE_EXTENSIONS[optimized_ext][0],
            ContentFile(optimized, name=str(Path(data.name).with_suffix(optimized_ext))),
            len(optimized),
        )

    def requested_dimensions(self):
        """Bounding box the client asked the stored image to fit into, if any."""
        width = self.request.POST.get("width")
        height = self.request.POST.get("height")
        if not (width and height):
            return None
        try:
            return int(width), int(height)
        except ValueError:
            return None


class ScheduleImportView(UploadMixin, View):
    permissions = {Permission.EVENT_UPDATE}
    ext_whitelist = (".xlsx",)
    max_size = settings.MAX_SIZE_CONFIG[SizeKey.UPLOAD_SIZE_XLSX]

    def post(self, request, *args, **kwargs):
        if not self.user:
            return  # triggers error already

        if "file" not in request.FILES:
            return upload_rejected(self.event, "file.missing")

        if request.FILES["file"].size > self.max_size:
            return upload_rejected(self.event, "file.size")

        if not any(
            request.FILES["file"].name.lower().endswith(e) for e in self.ext_whitelist
        ):
            return upload_rejected(self.event, "file.type")

        try:
            jsondata = convert(request.FILES["file"], timezone=self.event.timezone)
        except ValidationError as e:
            log_event('video', 'upload', OUTCOME_FAILURE, error_code='schedule_invalid', event_id=getattr(self.event, 'pk', None))
            return JsonResponse({"error": ", ".join(e)}, status=400)
        except ValueError as e:
            log_event('video', 'upload', OUTCOME_FAILURE, error_code='schedule_invalid', event_id=getattr(self.event, 'pk', None))
            return JsonResponse({"error": str(e)}, status=400)

        sf = StoredFile.objects.create(
            event=self.event,
            date=now(),
            filename=f'schedule_{now().strftime("%Y-%m-%d-%H-%M-%S")}.json',
            type="application/json",
            file=ContentFile(jsondata, "schedule.json"),
            public=True,
            user=self.user,
        )
        async_to_sync(notify_schedule_change)(self.event.id)
        return JsonResponse({"url": sf.file.url}, status=201)

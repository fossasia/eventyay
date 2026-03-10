import zoneinfo
from enum import StrEnum
from pathlib import Path


# The root directory of the project, where "./manage.py" file is located.
PROJECT_ROOT = Path(__file__).resolve().parent.parent

TIMEZONE_CHOICES = sorted(
    [tz for tz in zoneinfo.available_timezones() if not tz.startswith('Etc/') and tz != 'localtime']
)

# The directory for frontend development resources (node_modules, build scripts, etc.).
FRONTEND_DEV_DIR = PROJECT_ROOT / 'eventyay' / 'webapp'

# Default plugins enabled for new events
DEFAULT_PLUGINS = (
    'eventyay.plugins.sendmail',
    'eventyay.plugins.statistics',
    'eventyay.plugins.checkinlists',
)

# Email configuration constants
EVENTYAY_EMAIL_NONE_VALUE = 'info@eventyay.com'

# Stripe webhook URL paths.
# STRIPE_WEBHOOK_PATH is the canonical backend path, mounted under /api/v1/ in config/urls.py.
# STRIPE_WEBHOOK_LEGACY_PATH is the legacy path currently configured in the Stripe dashboard.
# TODO (#2463): Remove STRIPE_WEBHOOK_LEGACY_PATH and its URL alias in config/urls.py once
#              the Stripe dashboard endpoint has been updated to the canonical path.
STRIPE_WEBHOOK_PATH = 'webhook/stripe'
STRIPE_WEBHOOK_LEGACY_PATH = '_stripe/webhook'

class SizeKey(StrEnum):
    UPLOAD_SIZE_CSV = "upload_size_csv"
    UPLOAD_SIZE_IMAGE = "upload_size_image"
    UPLOAD_SIZE_PDF = "upload_size_pdf"
    UPLOAD_SIZE_XLSX = "upload_size_xlsx"
    UPLOAD_SIZE_FAVICON = "upload_size_favicon"
    UPLOAD_SIZE_ATTACHMENT = "upload_size_attachment"
    UPLOAD_SIZE_MAIL = "upload_size_mail"
    UPLOAD_SIZE_QUESTION = "upload_size_question"
    UPLOAD_SIZE_OTHER = "upload_size_other"

    RESPONSE_SIZE_WEBHOOK = "response_size_webhook"

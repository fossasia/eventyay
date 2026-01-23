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

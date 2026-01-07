import zoneinfo
from enum import StrEnum
from pathlib import Path

# The root directory of the project, where "./manage.py" file is located.
PROJECT_ROOT = Path(__file__).resolve().parent.parent

TIMEZONE_CHOICES = sorted(
    [tz for tz in zoneinfo.available_timezones() if not tz.startswith('Etc/') and tz != 'localtime']
)

# The directory for frontend development resources (node_modules, build scripts, etc.).
FRONTEND_DEV_DIR = PROJECT_ROOT / 'eventyay' / 'frontend'

class UploadSize(StrEnum):
    CSV = "csv"
    IMAGE = "image"
    PDF = "pdf"
    XLSX = "xlsx"
    FAVICON = "favicon"
    ATTACHMENT = "attachment"
    MAIL = "mail"
    QUESTION = "question"
    OTHER = "other"

class ResponseSize(StrEnum):
    WEBHOOK = "webhook"

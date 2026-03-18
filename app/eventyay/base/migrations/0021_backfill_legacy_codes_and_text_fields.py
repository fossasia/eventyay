from django.db import migrations
from django.db.models import Q
from django.utils.crypto import get_random_string


CODE_CHARSET = "ABCDEFGHJKLMNPQRSTUVWXYZ3789"
CODE_LENGTH = 6


def _generate_unique_user_code(User, existing_codes: set[str] | None = None) -> str:
    # Ensure case-insensitive uniqueness, matching GenerateCode semantics.
    while True:
        code = get_random_string(length=CODE_LENGTH, allowed_chars=CODE_CHARSET)
        lowered = code.lower()
        if existing_codes is not None:
            if lowered in existing_codes:
                continue
            # Final uniqueness safeguard against concurrent inserts.
            if User.objects.filter(code__iexact=code).exists():
                continue
            return code

        if not User.objects.filter(code__iexact=code).exists():
            return code


def forwards(apps, schema_editor):
    User = apps.get_model("base", "User")
    Submission = apps.get_model("base", "Submission")

    # Legacy databases can contain NULL abstracts/descriptions; normalize to empty string.
    Submission.objects.filter(abstract__isnull=True).update(abstract="")
    Submission.objects.filter(description__isnull=True).update(description="")

    # Legacy databases can contain users without a code. The schedule editor (and API consumers)
    # expect speakers to have a stable code, so we backfill them.
    missing_code_q = Q(code__isnull=True) | Q(code="")
    users_without_code = User.objects.filter(missing_code_q).only("id", "code")
    if not users_without_code.exists():
        return

    existing_codes = set(User.objects.exclude(missing_code_q).values_list("code", flat=True))
    existing_codes = {c.lower() for c in existing_codes if c}

    users_to_update = []
    for user in users_without_code.iterator():
        code = _generate_unique_user_code(User, existing_codes=existing_codes)
        existing_codes.add(code.lower())
        user.code = code
        users_to_update.append(user)

    if users_to_update:
        User.objects.bulk_update(users_to_update, ["code"])


def backwards(apps, schema_editor):
    # Backwards is a no-op: we cannot safely undo generated codes or distinguish backfilled
    # values from user-provided ones.
    return


class Migration(migrations.Migration):
    dependencies = [
        ("base", "0020_voucher_allow_ignore_approval_alter_event_currency_and_more"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]


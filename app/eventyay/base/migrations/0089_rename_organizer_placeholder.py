import re

from django.db import migrations


STORES = ('GlobalSettingsObject_SettingsStore', 'Organizer_SettingsStore', 'Event_SettingsStore')


def rename_placeholder(text, old, new):
    """Rename ``{old}`` to ``{new}`` in a stored email text, including the editor's ``data-variable`` chips."""
    if not text:
        return text
    text = text.replace(f'{{{old}}}', f'{{{new}}}')
    return re.sub(rf'(data-variable=\\?["\']){re.escape(old)}(\\?["\'])', rf'\g<1>{new}\g<2>', text)


def rename(apps, old, new):
    for store in STORES:
        model = apps.get_model('base', store)
        for setting in model.objects.filter(key__startswith='mail_', value__contains=old):
            value = rename_placeholder(setting.value, old, new)
            if value != setting.value:
                setting.value = value
                setting.save(update_fields=['value'])


def forwards(apps, schema_editor):
    rename(apps, 'organizer', 'organizer_name')


def backwards(apps, schema_editor):
    rename(apps, 'organizer_name', 'organizer')


class Migration(migrations.Migration):
    dependencies = [
        ('base', '0088_invoicevoucher_applies_to_platform_fees_budget_used'),
    ]

    operations = [
        migrations.RunPython(forwards, reverse_code=backwards),
    ]

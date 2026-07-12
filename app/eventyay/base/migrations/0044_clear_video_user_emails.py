from django.db import migrations


def clear_video_user_emails(apps, schema_editor):
    """Event-scoped video personas must not use User.email (platform accounts only)."""
    User = apps.get_model('base', 'User')
    User.objects.filter(event__isnull=False).exclude(email__isnull=True).update(email=None)


class Migration(migrations.Migration):
    dependencies = [
        ('base', '0043_remove_sendmail_from_plugins'),
    ]

    operations = [
        migrations.RunPython(clear_video_user_emails, migrations.RunPython.noop),
    ]

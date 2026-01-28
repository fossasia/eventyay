# Generated merge migration to resolve conflicting heads

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0009_event_private_testmode_and_more'),
        ('base', '0010_add_position_to_submissiontype'),
    ]

    operations = [
        # No operations needed - both migrations are independent
    ]

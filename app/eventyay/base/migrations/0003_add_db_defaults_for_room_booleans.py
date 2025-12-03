# Generated manually to add PostgreSQL DEFAULT constraints for room boolean fields
# Django's default= only works at the ORM level, not at the database level.
# This migration adds actual DEFAULT constraints in PostgreSQL.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0002_room_hidden_room_setup_complete_room_sidebar_hidden_and_more'),
    ]

    operations = [
        # Add DEFAULT FALSE for hidden column
        migrations.RunSQL(
            sql="ALTER TABLE base_room ALTER COLUMN hidden SET DEFAULT FALSE;",
            reverse_sql="ALTER TABLE base_room ALTER COLUMN hidden DROP DEFAULT;",
        ),
        # Add DEFAULT FALSE for setup_complete column
        migrations.RunSQL(
            sql="ALTER TABLE base_room ALTER COLUMN setup_complete SET DEFAULT FALSE;",
            reverse_sql="ALTER TABLE base_room ALTER COLUMN setup_complete DROP DEFAULT;",
        ),
        # Add DEFAULT TRUE for sidebar_hidden column
        migrations.RunSQL(
            sql="ALTER TABLE base_room ALTER COLUMN sidebar_hidden SET DEFAULT TRUE;",
            reverse_sql="ALTER TABLE base_room ALTER COLUMN sidebar_hidden DROP DEFAULT;",
        ),
        # Also add defaults for other boolean fields that may have the same issue
        migrations.RunSQL(
            sql="ALTER TABLE base_room ALTER COLUMN deleted SET DEFAULT FALSE;",
            reverse_sql="ALTER TABLE base_room ALTER COLUMN deleted DROP DEFAULT;",
        ),
        migrations.RunSQL(
            sql="ALTER TABLE base_room ALTER COLUMN force_join SET DEFAULT FALSE;",
            reverse_sql="ALTER TABLE base_room ALTER COLUMN force_join DROP DEFAULT;",
        ),
    ]


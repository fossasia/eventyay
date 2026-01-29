"""Fix missing DB column for Question.active.

Some databases can get into a state where migration 0009 is marked as applied, but the
physical `base_question.active` column is missing (e.g. faked/partial migration runs).

This migration is generated via `makemigrations --empty` and then filled with a safe
schema fix that uses Django's schema editor.

Note on reversibility: The reverse operation is intentionally a no-op to avoid
accidentally dropping the `active` column (and losing data) during rollbacks.
"""

from django.db import migrations
from django.db import models


def add_question_active_if_missing(apps, schema_editor):
    Question = apps.get_model('base', 'Question')
    table_name = Question._meta.db_table

    with schema_editor.connection.cursor() as cursor:
        columns = {
            col.name for col in schema_editor.connection.introspection.get_table_description(cursor, table_name)
        }

    model_field = Question._meta.get_field('active')

    # For large Postgres tables, adding a NOT NULL column with a default can rewrite the table.
    # Safer approach: add nullable column first (fast), backfill, then set NOT NULL.
    if 'active' not in columns:
        nullable_field = models.BooleanField(null=True)
        nullable_field.set_attributes_from_name(model_field.name)
        schema_editor.add_field(Question, nullable_field)

    # Backfill any NULLs (covers both: newly added nullable column and any existing nullable column)
    schema_editor.execute(
        f"UPDATE {schema_editor.quote_name(table_name)} SET {schema_editor.quote_name('active')} = TRUE "
        f"WHERE {schema_editor.quote_name('active')} IS NULL"
    )

    # Ensure the column matches the model (NOT NULL). This should not destroy data.
    nullable_field = models.BooleanField(null=True)
    nullable_field.set_attributes_from_name(model_field.name)
    schema_editor.alter_field(Question, nullable_field, model_field, strict=False)


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0009_event_private_testmode_and_more'),
    ]

    operations = [
        migrations.RunPython(
            add_question_active_if_missing,
            reverse_code=migrations.RunPython.noop,
        ),
    ]

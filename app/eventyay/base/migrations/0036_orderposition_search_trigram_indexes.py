from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.operations import AddIndexConcurrently, TrigramExtension
from django.db import migrations


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ('base', '0035_user_is_spam'),
    ]

    operations = [
        TrigramExtension(),
        AddIndexConcurrently(
            model_name='orderposition',
            index=GinIndex(
                fields=['attendee_name_cached'],
                name='orderpos_name_trgm',
                opclasses=['gin_trgm_ops'],
            ),
        ),
        AddIndexConcurrently(
            model_name='orderposition',
            index=GinIndex(
                fields=['attendee_email'],
                name='orderpos_email_trgm',
                opclasses=['gin_trgm_ops'],
            ),
        ),
        AddIndexConcurrently(
            model_name='order',
            index=GinIndex(
                fields=['code'],
                name='order_code_trgm',
                opclasses=['gin_trgm_ops'],
            ),
        ),
    ]

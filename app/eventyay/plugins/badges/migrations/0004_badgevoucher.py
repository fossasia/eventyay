import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('badges', '0003_badgelayout_allow_customization_and_more'),
        ('base', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='BadgeVoucher',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                (
                    'layout',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='voucher_assignments',
                        to='badges.badgelayout',
                    ),
                ),
                (
                    'voucher',
                    models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='badge_assignment',
                        to='base.voucher',
                    ),
                ),
            ],
            options={
                'ordering': ('id',),
            },
        ),
    ]

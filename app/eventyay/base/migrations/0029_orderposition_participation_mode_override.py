from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0028_product_participation_mode'),
    ]

    operations = [
        migrations.AddField(
            model_name='orderposition',
            name='participation_mode_override',
            field=models.CharField(
                blank=True,
                choices=[('virtual', 'Virtual (online)'), ('in_person', 'In-person')],
                help_text='If set, overrides the product-level participation mode for this position.',
                max_length=50,
                null=True,
                verbose_name='Participation mode override',
            ),
        ),
        migrations.AddField(
            model_name='cartposition',
            name='participation_mode_override',
            field=models.CharField(
                blank=True,
                choices=[('virtual', 'Virtual (online)'), ('in_person', 'In-person')],
                help_text='If set, overrides the product-level participation mode for this position.',
                max_length=50,
                null=True,
                verbose_name='Participation mode override',
            ),
        ),
    ]

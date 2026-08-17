import eventyay.base.models.poster
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0054_team_teamshifts_permissions'),
    ]

    operations = [
        migrations.AddField(
            model_name='poster',
            name='poster_file',
            field=models.FileField(
                blank=True,
                max_length=255,
                null=True,
                upload_to=eventyay.base.models.poster.poster_file_path,
                verbose_name='Poster File',
            ),
        ),
        migrations.AddField(
            model_name='poster',
            name='poster_preview_file',
            field=models.FileField(
                blank=True,
                max_length=255,
                null=True,
                upload_to=eventyay.base.models.poster.poster_preview_file_path,
                verbose_name='Poster Preview File',
            ),
        ),
        migrations.AlterField(
            model_name='poster',
            name='poster_url',
            field=models.URLField(blank=True, max_length=2048, null=True, verbose_name='Poster URL'),
        ),
        migrations.AlterField(
            model_name='poster',
            name='poster_preview',
            field=models.URLField(blank=True, max_length=2048, null=True, verbose_name='Poster Preview URL'),
        ),
    ]

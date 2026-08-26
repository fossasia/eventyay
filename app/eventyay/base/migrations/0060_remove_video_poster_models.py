from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0059_remove_video_exhibition_models'),
    ]

    operations = [
        # Child tables first so unique_together on PosterPresenter/PosterVote
        # is not altered after their FKs are gone.
        migrations.DeleteModel(
            name='PosterVote',
        ),
        migrations.DeleteModel(
            name='PosterPresenter',
        ),
        migrations.DeleteModel(
            name='PosterLink',
        ),
        migrations.DeleteModel(
            name='Poster',
        ),
    ]

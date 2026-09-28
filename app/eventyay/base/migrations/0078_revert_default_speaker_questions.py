from django.db import migrations
from django.db.models import QuerySet


def remove_default_speaker_questions(apps, schema_editor):
    """Remove the Job Title and Organization questions inserted by 0076.

    Answer and AnswerOption use on_delete=PROTECT, so their rows for these
    questions are removed first. Other custom questions are left in place.
    """
    TalkQuestion = apps.get_model('base', 'TalkQuestion')
    Answer = apps.get_model('base', 'Answer')
    AnswerOption = apps.get_model('base', 'AnswerOption')

    questions = QuerySet(model=TalkQuestion).filter(
        import_key__in=['speaker_job_title', 'speaker_organization'],
    )
    QuerySet(model=Answer).filter(question__in=questions).delete()
    QuerySet(model=AnswerOption).filter(question__in=questions).delete()
    questions.delete()


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0077_admin_message_center'),
    ]

    operations = [
        migrations.RunPython(remove_default_speaker_questions, reverse_code=migrations.RunPython.noop),
    ]

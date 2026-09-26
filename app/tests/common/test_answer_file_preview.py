import pytest
from django.template.loader import render_to_string

from eventyay.base.models import Answer, TalkQuestion, TalkQuestionVariant
from eventyay.common.forms.widgets import AnswerFileInput


IMAGE_PATH = 'testevent/question_uploads/speaker_photo_ab12cd3.jpg'
IMAGE_URL = '/media/testevent/question_uploads/speaker_photo_ab12cd3.jpg'
DOCUMENT_PATH = 'testevent/question_uploads/slides_ab12cd3.pdf'
DOCUMENT_URL = '/media/testevent/question_uploads/slides_ab12cd3.pdf'


class StubFile:
    """Stands in for a stored ``FieldFile`` without touching the storage backend."""

    def __init__(self, name, url):
        self.name = name
        self.url = url


def build_answer(file_path):
    answer = Answer(question=TalkQuestion(question='Speaker image', variant=TalkQuestionVariant.FILE))
    if file_path:
        answer.answer_file = file_path
    return answer


@pytest.mark.parametrize(
    'file_path,expected',
    (
        (IMAGE_PATH, True),
        ('testevent/question_uploads/photo_ab12cd3.PNG', True),
        ('testevent/question_uploads/logo_ab12cd3.svg', True),
        (DOCUMENT_PATH, False),
        ('testevent/question_uploads/notes_ab12cd3.txt', False),
        ('', False),
    ),
)
def test_answer_file_is_image(file_path, expected):
    assert build_answer(file_path).answer_file_is_image is expected


def test_answer_file_name_drops_the_upload_path():
    assert build_answer(IMAGE_PATH).answer_file_name == 'speaker_photo_ab12cd3.jpg'
    assert build_answer('').answer_file_name == ''


def test_answer_display_renders_images_inline():
    html = render_to_string('common/includes/answer_file.html', {'answer': build_answer(IMAGE_PATH)})
    assert '<img' in html
    assert 'testevent/question_uploads' not in html.replace(IMAGE_URL, '')
    assert IMAGE_URL in html


def test_answer_display_links_other_files_by_name():
    html = render_to_string('common/includes/answer_file.html', {'answer': build_answer(DOCUMENT_PATH)})
    assert '<img' not in html
    assert 'slides_ab12cd3.pdf' in html
    assert 'question_uploads/slides_ab12cd3.pdf</a>' not in html


def test_answer_display_shows_empty_state_without_a_file():
    html = render_to_string('common/includes/answer_file.html', {'answer': build_answer('')})
    assert '<img' not in html
    assert '<a' not in html
    assert 'No file uploaded.' in html


def render_widget(value, required=False):
    widget = AnswerFileInput(attrs={'alt': 'Speaker image'})
    widget.is_required = required
    return widget.render('question_1', value, attrs={'id': 'id_question_1'})


def test_widget_previews_the_current_image_instead_of_its_name():
    html = render_widget(StubFile(IMAGE_PATH, IMAGE_URL))
    assert f'src="{IMAGE_URL}"' in html
    assert f'data-initial-src="{IMAGE_URL}"' in html
    assert 'Change image' in html
    assert 'Currently' not in html
    assert 'speaker_photo_ab12cd3.jpg<' not in html
    assert 'alt="Speaker image"' in html
    assert 'alt="Speaker image" type="file"' not in html


def test_widget_keeps_a_named_link_for_other_files():
    html = render_widget(StubFile(DOCUMENT_PATH, DOCUMENT_URL))
    assert f'src="{DOCUMENT_URL}"' not in html
    assert 'slides_ab12cd3.pdf' in html
    assert 'Change file' in html


def test_widget_without_a_current_file_only_offers_the_upload_control():
    html = render_widget(None)
    assert 'type="file"' in html
    assert 'Change image' not in html
    assert 'Change file' not in html
    assert 'form-image-preview d-none' in html.replace('answer-file-input-preview ', '')


def test_widget_hides_the_clear_checkbox_for_required_questions():
    assert 'question_1-clear' in render_widget(StubFile(IMAGE_PATH, IMAGE_URL))
    assert 'question_1-clear' not in render_widget(StubFile(IMAGE_PATH, IMAGE_URL), required=True)

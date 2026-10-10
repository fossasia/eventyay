from io import BytesIO

import pytest
from django import forms
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils.timezone import now
from PIL import Image

from eventyay.base.models import Answer, Event, Organizer, TalkQuestion, TalkQuestionVariant
from eventyay.common.forms.mixins import QuestionFieldsMixin
from phonenumber_field.phonenumber import PhoneNumber


class DummyForm(QuestionFieldsMixin, forms.Form):
    def __init__(self, event, *args, **kwargs):
        self.event = event
        super().__init__(*args, **kwargs)


@pytest.mark.django_db
class TestQuestionFieldsMixinPhoneInitialization:
    @pytest.fixture
    def event(self):
        o = Organizer.objects.create(name='Dummy', slug='dummy')
        return Event.objects.create(
            organizer=o,
            name="Test Event",
            slug="test-event",
            date_from=now(),
        )

    @pytest.fixture
    def question(self, event):
        return TalkQuestion.objects.create(
            event=event,
            question="Phone?",
            variant=TalkQuestionVariant.PHONE_NUMBER,
        )

    def test_saved_valid_number(self, event, question):
        form = DummyForm(event=event)
        field = form.get_field(
            question=question,
            initial="+12025550123",
            initial_object=None,
            readonly=False
        )
        assert field.initial == PhoneNumber.from_string("+12025550123")

    def test_invalid_saved_number(self, event, question):
        form = DummyForm(event=event)
        field = form.get_field(
            question=question,
            initial="invalid_number",
            initial_object=None,
            readonly=False
        )
        assert field.initial is None

    def test_resolvable_default_country(self, event, question):
        # Set invoice_address_from_country to US for default prefix +1
        event.settings.invoice_address_from_country = "US"
        form = DummyForm(event=event)
        field = form.get_field(
            question=question,
            initial=None,
            initial_object=None,
            readonly=False
        )
        assert field.initial == "+1."

    def test_event_no_default_country(self, event, question):
        # Empty settings, no country
        event.settings.invoice_address_from_country = None
        event.settings.region = None
        form = DummyForm(event=event)
        field = form.get_field(
            question=question,
            initial=None,
            initial_object=None,
            readonly=False
        )
        assert field.initial is None

    def test_custom_question_image_is_saved_as_webp(self, event):
        question = TalkQuestion.objects.create(
            event=event,
            question='Upload an image',
            variant=TalkQuestionVariant.FILE,
        )
        image = Image.new('RGB', (2000, 1000), 'red')
        image_bytes = BytesIO()
        image.save(image_bytes, format='PNG')
        upload = SimpleUploadedFile('speaker.png', image_bytes.getvalue(), content_type='image/png')
        field = forms.FileField()
        field.question = question
        answer = Answer(question=question, answer='')

        DummyForm(event=event)._save_to_answer(field, answer, upload)

        assert answer.answer_file.name.endswith('.webp')
        assert answer.answer == f'file://{answer.answer_file.name}'
        assert Image.open(answer.answer_file).format == 'WEBP'

    def test_custom_question_document_is_not_reencoded(self, event):
        question = TalkQuestion.objects.create(
            event=event,
            question='Upload a document',
            variant=TalkQuestionVariant.FILE,
        )
        upload = SimpleUploadedFile('slides.pdf', b'%PDF-1.7', content_type='application/pdf')
        field = forms.FileField()
        field.question = question
        answer = Answer(question=question, answer='')

        DummyForm(event=event)._save_to_answer(field, answer, upload)

        assert answer.answer_file.name.endswith('.pdf')
        assert answer.answer_file.read() == b'%PDF-1.7'

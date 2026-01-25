
import pytest
from django_scopes import scope
from django.core.files.uploadedfile import SimpleUploadedFile
from eventyay.base.models import User

@pytest.mark.django_db
def test_avatar_url_changes_on_update(orga_client, speaker, event, submission_type):
    from eventyay.base.models import Submission
    with scope(event=event):
        # Speaker must have a submission to be visible in orga speaker views
        Submission.objects.create(
            event=event,
            title="Test Submission",
            submission_type=submission_type,
            state="submitted",
        ).speakers.add(speaker)
        url = speaker.event_profile(event).orga_urls.base
    
    # Create a valid image file
    from io import BytesIO
    from PIL import Image
    
    def create_image(color='white'):
        file = BytesIO()
        image = Image.new('RGB', (100, 100), color)
        image.save(file, 'PNG')
        file.name = 'test.png'
        file.seek(0)
        return file.getvalue()

    # Upload first avatar
    avatar1 = SimpleUploadedFile("avatar1.png", create_image('white'), content_type="image/png")
    response = orga_client.post(
        url,
        data={
            "fullname": speaker.name,
            "email": speaker.email,
            "biography": "Best speaker in the world.",
            "avatar": avatar1,
        },
        follow=True,
    )
    if response.status_code != 200 or 'form' in response.context and response.context['form'].errors:
        print(f"Form errors: {response.context['form'].errors if 'form' in response.context else 'No form in context'}")
        if 'questions_form' in response.context:
            print(f"Question form errors: {response.context['questions_form'].errors}")
    assert response.status_code == 200
    
    with scope(event=event):
        speaker.refresh_from_db()
        if not speaker.avatar:
            print(f"Speaker avatar is still None after first upload. User PK: {speaker.pk}")
        assert speaker.avatar
        url1 = speaker.avatar.url
        print(f"URL 1: {url1}")

    # Upload second avatar
    avatar2 = SimpleUploadedFile("avatar2.png", create_image('black'), content_type="image/png")
    response = orga_client.post(
        url,
        data={
            "fullname": speaker.name,
            "email": speaker.email,
            "biography": "Best speaker in the world.",
            "avatar": avatar2,
        },
        follow=True,
    )
    if response.status_code != 200 or 'form' in response.context and response.context['form'].errors:
        print(f"Second POST Form errors: {response.context['form'].errors if 'form' in response.context else 'No form in context'}")
    assert response.status_code == 200
    
    with scope(event=event):
        speaker.refresh_from_db()
        url2 = speaker.avatar.url
        print(f"URL 2: {url2}")
    
    # Check if URL changed
    assert url1 != url2, "Avatar URL did not change after update, causing browser cache issues"

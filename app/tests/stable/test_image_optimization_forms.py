import pytest
from io import BytesIO
from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils.datastructures import MultiValueDict
from django_scopes import scope
from eventyay.submission.forms.submission import InfoForm
from eventyay.person.forms.profile import SpeakerProfileForm
from eventyay.base.models import Submission, User, SpeakerProfile, SubmissionType

def _create_test_image(color="red", format="PNG", width=100, height=100):
    img = Image.new("RGB", (width, height), color)
    buf = BytesIO()
    img.save(buf, format=format)
    buf.seek(0)
    return SimpleUploadedFile(f"test.{format.lower()}", buf.read(), content_type=f"image/{format.lower()}")

@pytest.mark.django_db
def test_info_form_clean_image_with_new_upload(event, settings):
    settings.IMAGE_DEFAULT_MAX_WIDTH = 1000
    settings.IMAGE_DEFAULT_MAX_HEIGHT = 1000
    
    upload = _create_test_image()
    with scope(event=event):
        form = InfoForm(
            event=event,
            data={'title': 'Test submission', 'abstract': 'Test abstract', 'content_locale': 'en'},
            files=MultiValueDict({'image': [upload]})
        )
        
        # We only care about the clean_image part. Even if the form is invalid for other reasons,
        # clean_image runs if the field itself is valid so far. We can just call is_valid()
        form.is_valid()
        
        # Check if 'image' is in cleaned_data and it got optimized
        cleaned_image = form.cleaned_data.get('image')
        assert cleaned_image is not None
        assert cleaned_image.name.endswith('.webp')
        assert cleaned_image.content_type == 'image/webp'

@pytest.mark.django_db
def test_info_form_clean_image_without_new_upload(event):
    # Setup submission with an existing image
    with scope(event=event):
        sub_type = SubmissionType(event=event, name="Test Type")
        submission = Submission(event=event, title="Existing", submission_type=sub_type, pk=1)
        existing_image = _create_test_image()
        submission.image.save('test.png', existing_image, save=False)
        
        # Form submitted without 'image' in files
        form = InfoForm(
            event=event,
            instance=submission,
            data={'title': 'Test submission', 'abstract': 'Test abstract', 'content_locale': 'en'},
            files=MultiValueDict({})
        )
        
        form.is_valid()
        cleaned_image = form.cleaned_data.get('image')
        
        # It should return the original image untouched
        assert cleaned_image == submission.image

@pytest.mark.django_db
def test_speaker_profile_form_clean_avatar_with_new_upload(user, event, settings):
    settings.IMAGE_DEFAULT_MAX_WIDTH = 1000
    settings.IMAGE_DEFAULT_MAX_HEIGHT = 1000
    
    with scope(event=event):
        profile, _ = SpeakerProfile.objects.get_or_create(user=user, event=event)
        
        upload = _create_test_image()
        form = SpeakerProfileForm(
            user=user,
            event=event,
            instance=profile,
            data={'name': 'Test User', 'email': user.email},
            files=MultiValueDict({'avatar': [upload]})
        )
        
        form.is_valid()
        
        cleaned_avatar = form.cleaned_data.get('avatar')
        assert cleaned_avatar is not None
        assert cleaned_avatar.name.endswith('.webp')
        assert cleaned_avatar.content_type == 'image/webp'

@pytest.mark.django_db
def test_speaker_profile_form_clean_avatar_without_new_upload(user, event):
    with scope(event=event):
        profile, _ = SpeakerProfile.objects.get_or_create(user=user, event=event)
        existing_avatar = _create_test_image()
        profile.avatar.save('avatar.png', existing_avatar)
        
        form = SpeakerProfileForm(
            user=user,
            event=event,
            instance=profile,
            data={'name': 'Test User', 'email': user.email},
            files=MultiValueDict({})
        )
        
        form.is_valid()
        cleaned_avatar = form.cleaned_data.get('avatar')
        
        assert cleaned_avatar == profile.avatar

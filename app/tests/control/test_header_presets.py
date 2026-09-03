import io
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils.timezone import now
from PIL import Image

from eventyay.base.header_presets import get_active_presets, invalidate_preset_cache
from eventyay.base.models import EventHeaderPreset, EventHeaderPresetCategory, User


def _create_test_image(width=1920, height=640):
    out = io.BytesIO()
    im = Image.new('RGB', (width, height), color=(100, 150, 200))
    im.save(out, format='JPEG')
    out.seek(0)
    return SimpleUploadedFile('sample_preset.jpg', out.read(), content_type='image/jpeg')


@pytest.fixture
def admin_user(client):
    user = User.objects.create_superuser('admin_preset@test.org', 'adminpass123')
    client.force_login(user)
    user.staffsession_set.create(date_start=now(), session_key=client.session.session_key)
    return user


@pytest.fixture
def test_category():
    cat, _ = EventHeaderPresetCategory.objects.get_or_create(
        name='Abstract Test',
    )
    return cat


@pytest.mark.django_db
def test_admin_preset_list_view(client, admin_user, test_category):
    preset = EventHeaderPreset.objects.create(
        name='Test Preset Alpha',
        category=test_category,
        image=_create_test_image(),
        thumbnail=_create_test_image(),
        is_active=True,
    )
    invalidate_preset_cache()

    url = reverse('eventyay_admin:admin.header_presets')
    response = client.get(url)
    assert response.status_code == 200
    assert 'presets' in response.context
    assert 'categories' in response.context
    assert 'total_presets_count' in response.context
    assert preset in response.context['presets']


@pytest.mark.django_db
def test_admin_preset_create_view(client, admin_user, test_category):
    url = reverse('eventyay_admin:admin.header_presets.add')
    test_image = _create_test_image(1200, 400)

    data = {
        'name_0': 'Admin Uploaded Sunset',
        'category': test_category.pk,
        'image': test_image,
        'is_active': 'on',
    }
    response = client.post(url, data)
    assert response.status_code == 302

    preset = EventHeaderPreset.objects.filter(name__icontains='Admin Uploaded Sunset').first()
    assert preset is not None
    assert preset.image is not None
    assert preset.thumbnail is not None
    assert preset.is_active is True
    assert preset in get_active_presets()


@pytest.mark.django_db
def test_admin_preset_create_invalid_image_fails(client, admin_user, test_category):
    url = reverse('eventyay_admin:admin.header_presets.add')
    fake_file = SimpleUploadedFile('malicious.txt', b'this is not an image file', content_type='text/plain')

    data = {
        'name_0': 'Invalid Image Preset',
        'category': test_category.pk,
        'image': fake_file,
        'is_active': 'on',
    }
    response = client.post(url, data)
    assert response.status_code == 200
    assert 'form' in response.context
    assert 'image' in response.context['form'].errors


@pytest.mark.django_db
def test_admin_preset_update_view(client, admin_user, test_category):
    preset = EventHeaderPreset.objects.create(
        name='Original Preset Name',
        category=test_category,
        image=_create_test_image(),
        thumbnail=_create_test_image(),
        is_active=True,
    )

    url = reverse('eventyay_admin:admin.header_presets.edit', kwargs={'pk': preset.pk})
    data = {
        'name_0': 'Updated Preset Name',
        'category': test_category.pk,
        'is_active': 'on',
    }
    response = client.post(url, data)
    assert response.status_code == 302

    preset.refresh_from_db()
    assert 'Updated Preset Name' in str(preset.name)


@pytest.mark.django_db
def test_admin_preset_toggle_active(client, admin_user, test_category):
    preset = EventHeaderPreset.objects.create(
        name='Toggleable Preset',
        category=test_category,
        image=_create_test_image(),
        thumbnail=_create_test_image(),
        is_active=True,
    )

    url = reverse('eventyay_admin:admin.header_presets.toggle', kwargs={'pk': preset.pk})
    response = client.post(url)
    assert response.status_code == 302

    preset.refresh_from_db()
    assert preset.is_active is False

    # Toggle back
    response = client.post(url)
    assert response.status_code == 302
    preset.refresh_from_db()
    assert preset.is_active is True


@pytest.mark.django_db
def test_admin_preset_delete_view(client, admin_user, test_category):
    preset = EventHeaderPreset.objects.create(
        name='To Be Deleted Preset',
        category=test_category,
        image=_create_test_image(),
        thumbnail=_create_test_image(),
        is_active=True,
    )

    url = reverse('eventyay_admin:admin.header_presets.delete', kwargs={'pk': preset.pk})
    response = client.post(url)
    assert response.status_code == 302

    assert not EventHeaderPreset.objects.filter(pk=preset.pk).exists()


@pytest.mark.django_db
def test_admin_preset_category_crud(client, admin_user):
    # 1. Create category
    add_url = reverse('eventyay_admin:admin.header_presets.category.add')
    data = {
        'name_0': 'Sci-Fi Futuristic',
    }
    response = client.post(add_url, data)
    assert response.status_code == 302

    cat = EventHeaderPresetCategory.objects.filter(name__icontains='Sci-Fi Futuristic').first()
    assert cat is not None
    assert 'Sci-Fi Futuristic' in str(cat.name)

    # 2. Edit category
    edit_url = reverse('eventyay_admin:admin.header_presets.category.edit', kwargs={'pk': cat.pk})
    data = {
        'name_0': 'Sci-Fi Renamed',
    }
    response = client.post(edit_url, data)
    assert response.status_code == 302
    cat.refresh_from_db()
    assert 'Sci-Fi Renamed' in str(cat.name)

    # 3. Delete category
    delete_url = reverse('eventyay_admin:admin.header_presets.category.delete', kwargs={'pk': cat.pk})
    response = client.post(delete_url)
    assert response.status_code == 302
    assert not EventHeaderPresetCategory.objects.filter(pk=cat.pk).exists()

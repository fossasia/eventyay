
import pytest
import uuid
from eventyay.base.models import User

@pytest.mark.django_db
def test_soft_delete_anonymization():
    # Create a dummy user
    email_original = f"test_user_{uuid.uuid4()}@example.com"
    user = User.objects.create(
        email=email_original,
        fullname="Original Name",
        wikimedia_username="WikiUser",
        is_active=True
    )
    
    # Create a SocialAccount linked to user
    from allauth.socialaccount.models import SocialAccount
    SocialAccount.objects.create(user=user, provider='mediawiki', uid='12345')

    user_id = user.id
    
    # Perform soft delete
    user.soft_delete()
    
    # Reload from DB
    user.refresh_from_db()
    
    # Verify Anonymization
    assert user.deleted is True
    assert "deleted_" in user.email
    assert user.fullname == "Deleted User" # This should still pass if locale is EN
    assert user.wikimedia_username is None
    
    # Verify SocialAccount deletion
    assert not SocialAccount.objects.filter(user=user).exists()

    
    # Verify original email is free (optional, but good check)
    with pytest.raises(User.DoesNotExist):
        User.objects.get(email=email_original)

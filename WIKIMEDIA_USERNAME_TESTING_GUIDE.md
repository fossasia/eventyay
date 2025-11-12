# Wikimedia Username Population - Testing Guide

## Overview
This guide documents how to test the wikimedia_username field population after OAuth login.

## Changes Implemented

### File: `app/eventyay/plugins/socialauth/adapter.py`

Added `pre_social_login()` method to `CustomSocialAccountAdapter`:

```python
def pre_social_login(self, request, sociallogin):
    """
    Invoked after a user successfully authenticates via a social provider,
    but before the login is fully processed.
    
    This is the ideal place to extract and populate the wikimedia_username
    from the OAuth provider's extra_data.
    
    Fixes issue #1214: SSO Username Mapping
    """
    # Only process MediaWiki logins
    if sociallogin.account.provider != 'mediawiki':
        logger.debug(f'Skipping pre_social_login for provider: {sociallogin.account.provider}')
        return

    # Extract extra_data from the social account
    extra_data = sociallogin.account.extra_data
    logger.info(f'Processing MediaWiki OAuth login. extra_data keys: {list(extra_data.keys())}')

    # Extract wikimedia username from extra_data
    wikimedia_username = extra_data.get('username') or extra_data.get('realname') or ''
    
    if wikimedia_username:
        logger.info(f'Extracted wikimedia_username: {wikimedia_username}')
        
        # Populate the user's wikimedia_username field
        user = sociallogin.user
        user.wikimedia_username = wikimedia_username
        
        # Save if user already exists (update case)
        if user.pk:
            user.save(update_fields=['wikimedia_username'])
            logger.info(f'Updated existing user {user.email} with wikimedia_username: {wikimedia_username}')
        else:
            logger.info(f'Will create new user with wikimedia_username: {wikimedia_username}')
    else:
        logger.warning(f'Could not extract wikimedia_username from extra_data: {extra_data}')
```

## Testing Prerequisites

1. **MediaWiki OAuth Application**: Must be configured in `/control/global/social_auth/`
   - Consumer Key and Secret set up
   - Callback URL: `http://localhost:8000/accounts/mediawiki/login/callback/`

2. **Wikimedia Account**: Test account on Wikipedia/Wikimedia Commons

3. **Docker Environment**: Application running at `http://localhost:8000`

## Manual Testing Procedure

### Test Case 1: New User Login (Account Creation)

**Steps:**
1. Clear browser cookies/use incognito mode
2. Navigate to: `http://localhost:8000/oauth_login/mediawiki/`
3. Authorize the application on MediaWiki
4. Complete the OAuth flow

**Expected Results:**
- User is created in the database
- `wikimedia_username` field is populated with the MediaWiki username
- Logs show:
  ```
  INFO Processing MediaWiki OAuth login. extra_data keys: [...]
  INFO Extracted wikimedia_username: <username>
  INFO Will create new user with wikimedia_username: <username>
  ```

**Verification:**
```bash
# Enter Docker container
docker compose exec web bash

# Open Django shell
python manage.py shell

# Check user
from eventyay.base.models import User
user = User.objects.filter(email='<your-email>').first()
print(f"Email: {user.email}")
print(f"Wikimedia Username: {user.wikimedia_username}")
```

### Test Case 2: Existing User Login (Update)

**Steps:**
1. Login with existing account that has empty `wikimedia_username`
2. Navigate to: `http://localhost:8000/oauth_login/mediawiki/`
3. Authorize the application
4. Complete the OAuth flow

**Expected Results:**
- Existing user is updated
- `wikimedia_username` field is populated
- Logs show:
  ```
  INFO Processing MediaWiki OAuth login. extra_data keys: [...]
  INFO Extracted wikimedia_username: <username>
  INFO Updated existing user <email> with wikimedia_username: <username>
  ```

**Verification:**
```bash
# Check updated user in Django shell
from eventyay.base.models import User
user = User.objects.filter(email='<your-email>').first()
print(f"Wikimedia Username: {user.wikimedia_username}")
```

### Test Case 3: Username Change on MediaWiki

**Steps:**
1. Change username on MediaWiki (if possible, or use different account)
2. Login again via OAuth
3. Complete the flow

**Expected Results:**
- `wikimedia_username` is updated to new value
- Logs show update message

### Test Case 4: Missing Username in extra_data (Edge Case)

**Setup:**
Mock or modify the OAuth response to omit username fields.

**Expected Results:**
- Warning logged:
  ```
  WARNING Could not extract wikimedia_username from extra_data: {...}
  ```
- User is still created/logged in (doesn't break flow)
- `wikimedia_username` remains empty/null

## Automated Testing (Future)

### Unit Test Structure (To be implemented)

```python
# test_socialauth_adapter.py

from django.test import TestCase, RequestFactory
from allauth.socialaccount.models import SocialLogin, SocialAccount
from eventyay.plugins.socialauth.adapter import CustomSocialAccountAdapter
from eventyay.base.models import User


class WikimediaUsernamePopulationTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.adapter = CustomSocialAccountAdapter()
    
    def test_new_user_wikimedia_username_populated(self):
        """Test wikimedia_username is populated for new user"""
        # Setup mock sociallogin with extra_data
        social_account = SocialAccount(provider='mediawiki', extra_data={'username': 'TestUser123'})
        sociallogin = SocialLogin(account=social_account, user=User(email='test@example.com'))
        
        # Call pre_social_login
        request = self.factory.get('/')
        self.adapter.request = request
        self.adapter.pre_social_login(request, sociallogin)
        
        # Assert wikimedia_username is set
        self.assertEqual(sociallogin.user.wikimedia_username, 'TestUser123')
    
    def test_existing_user_wikimedia_username_updated(self):
        """Test wikimedia_username is updated for existing user"""
        # Create existing user
        user = User.objects.create(email='existing@example.com', wikimedia_username='')
        
        # Setup mock sociallogin
        social_account = SocialAccount(provider='mediawiki', extra_data={'username': 'UpdatedUser'})
        sociallogin = SocialLogin(account=social_account, user=user)
        
        # Call pre_social_login
        request = self.factory.get('/')
        self.adapter.request = request
        self.adapter.pre_social_login(request, sociallogin)
        
        # Assert wikimedia_username is updated
        user.refresh_from_db()
        self.assertEqual(user.wikimedia_username, 'UpdatedUser')
    
    def test_fallback_to_realname(self):
        """Test fallback to 'realname' field if 'username' not present"""
        social_account = SocialAccount(provider='mediawiki', extra_data={'realname': 'Real Name'})
        sociallogin = SocialLogin(account=social_account, user=User(email='test@example.com'))
        
        request = self.factory.get('/')
        self.adapter.request = request
        self.adapter.pre_social_login(request, sociallogin)
        
        self.assertEqual(sociallogin.user.wikimedia_username, 'Real Name')
    
    def test_non_mediawiki_provider_skipped(self):
        """Test that non-MediaWiki providers are skipped"""
        social_account = SocialAccount(provider='github', extra_data={'username': 'GitHubUser'})
        sociallogin = SocialLogin(account=social_account, user=User(email='test@example.com'))
        
        request = self.factory.get('/')
        self.adapter.request = request
        self.adapter.pre_social_login(request, sociallogin)
        
        # wikimedia_username should not be set for non-MediaWiki providers
        self.assertIsNone(sociallogin.user.wikimedia_username)
```

## Log Monitoring

### Tail Docker logs during testing:

```bash
# Follow logs in real-time
docker compose logs -f web

# Filter for socialauth logs
docker compose logs -f web | grep socialauth

# Filter for wikimedia_username logs
docker compose logs -f web | grep wikimedia_username
```

### Expected Log Output (Success):

```
INFO eventyay.plugins.socialauth.adapter Processing MediaWiki OAuth login. extra_data keys: ['username', 'sub', 'editcount', 'confirmed_email', ...]
INFO eventyay.plugins.socialauth.adapter Extracted wikimedia_username: JohnDoe123
INFO eventyay.plugins.socialauth.adapter Updated existing user john@example.com with wikimedia_username: JohnDoe123
```

### Expected Log Output (Missing Username):

```
INFO eventyay.plugins.socialauth.adapter Processing MediaWiki OAuth login. extra_data keys: ['sub', 'editcount', 'confirmed_email', ...]
WARNING eventyay.plugins.socialauth.adapter Could not extract wikimedia_username from extra_data: {'sub': '...', 'editcount': 42, ...}
```

## Database Verification

### SQL Query to Check wikimedia_username Population:

```sql
-- Connect to database
docker compose exec db psql -U eventyay eventyay

-- Check users with wikimedia_username
SELECT id, email, fullname, wikimedia_username, date_joined
FROM base_user
WHERE wikimedia_username IS NOT NULL AND wikimedia_username != '';

-- Check social accounts linked to users
SELECT 
    u.email, 
    u.wikimedia_username,
    sa.provider,
    sa.extra_data->>'username' as oauth_username,
    sa.extra_data->>'realname' as oauth_realname
FROM base_user u
JOIN socialaccount_socialaccount sa ON u.id = sa.user_id
WHERE sa.provider = 'mediawiki';
```

## Success Criteria

- ✅ `pre_social_login()` is called during MediaWiki OAuth flow
- ✅ `wikimedia_username` is extracted from `extra_data['username']`
- ✅ Fallback to `extra_data['realname']` works
- ✅ New users have `wikimedia_username` populated
- ✅ Existing users have `wikimedia_username` updated
- ✅ Non-MediaWiki providers are skipped
- ✅ Comprehensive logging shows extraction process
- ✅ No errors or exceptions during OAuth flow

## Troubleshooting

### Issue: wikimedia_username still empty after login

**Possible Causes:**
1. `pre_social_login()` not being called → Check adapter is configured in settings
2. `extra_data` doesn't contain username → Check MediaWiki OAuth scope
3. Exception during save → Check logs for errors

**Debug Steps:**
```bash
# Check if adapter is configured
grep -r "SOCIALACCOUNT_ADAPTER" app/eventyay/*/settings.py

# Enable DEBUG logging
# In app/eventyay/config/settings.py, set:
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'eventyay.plugins.socialauth': {
            'handlers': ['console'],
            'level': 'DEBUG',
        },
    },
}
```

### Issue: MediaWiki OAuth extra_data structure unknown

**Debug:**
Add temporary logging to see full extra_data:

```python
# In adapter.py, add after line 55:
logger.info(f'FULL extra_data: {json.dumps(extra_data, indent=2)}')
```

## Next Steps

After confirming wikimedia_username population works:

1. **CSV Export Feature** (#1214)
   - Add wikimedia_username to CSV exports
   - Add per-event toggle for "Use Wikimedia username as public name"

2. **Trust & Safety Fields** (#1214)
   - Add `original_sso_username` field (non-editable, admin-only)
   - Ensure it's stored on first login and never changed

3. **UI Updates**
   - Show wikimedia_username in user profile
   - Allow organizers to export wikimedia_username for their events

4. **Documentation**
   - Update user guide for SSO username mapping
   - Document privacy implications

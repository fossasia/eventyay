# Wikimedia Username Population Fix - Implementation Plan

## Problem Analysis

### Current Issue
After successful MediaWiki OAuth login, the `wikimedia_username` field in the User model is not being populated with data.

### Root Cause Investigation

1. **OAuthReturnView Flow Problem**:
   - `OAuthReturnView.get_or_create_user()` tries to access `request.user.socialaccount_set`
   - At this point, `request.user` might not be authenticated yet or might be AnonymousUser
   - The social account might not be created yet in django-allauth's flow

2. **Django-allauth Flow**:
   - Standard django-allauth creates the social account in its own views
   - Custom views like `OAuthReturnView` might be called at the wrong time
   - Need to integrate with allauth's signals or adapter methods

### Solution Strategy

#### Option 1: Use Django-allauth Signals (RECOMMENDED)
Hook into allauth's `pre_social_login` or `social_account_added` signal to populate `wikimedia_username`.

**Pros**:
- Works with standard allauth flow
- Guaranteed to fire after social account is created
- Clean separation of concerns

**Cons**:
- Requires understanding allauth signal system

#### Option 2: Override CustomSocialAccountAdapter
Extend the `pre_social_login()` or `populate_user()` method in the adapter.

**Pros**:
- Already have CustomSocialAccountAdapter
- Centralized in one place

**Cons**:
- Adapter might be called before user is created

#### Option 3: Fix OAuthReturnView Timing
Ensure the view is called after allauth completes its flow.

**Pros**:
- Keep custom flow

**Cons**:
- May conflict with allauth's internal flow

## Implementation Plan

### Phase 1: Debug Current Flow
1. Add comprehensive logging to understand when each method is called
2. Log `request.user` state at different points
3. Log social account creation and `extra_data` content

### Phase 2: Implement Fix Using Allauth Signals
1. Create signal receiver for `allauth.socialaccount.signals.pre_social_login`
2. In signal handler:
   - Extract username from `sociallogin.account.extra_data`
   - Update `user.wikimedia_username`
   - Save user
3. Register signal in app config

### Phase 3: Add Logging and Error Handling
1. Log when username is successfully extracted
2. Log when username extraction fails (with reason)
3. Handle cases where username is not in extra_data

### Phase 4: Testing
1. Test with fresh user (account creation)
2. Test with existing user (account update)
3. Test with user changing Wikimedia username
4. Verify `wikimedia_username` is populated in database

### Phase 5: CSV Export Feature
1. Add `wikimedia_username` to CSV export
2. Add per-event toggle for "Use Wikimedia username as public name"
3. Add `original_sso_username` field (non-editable)
4. Implement admin-only view of original username

## Files to Modify

1. **`app/eventyay/plugins/socialauth/signals.py`** (NEW)
   - Create signal handlers for social account events

2. **`app/eventyay/plugins/socialauth/apps.py`**
   - Register signal handlers in app ready()

3. **`app/eventyay/plugins/socialauth/adapter.py`**
   - Add username extraction in pre_social_login()

4. **`app/eventyay/plugins/socialauth/views.py`**
   - Add logging to debug current flow
   - Potentially simplify OAuthReturnView

5. **`app/eventyay/base/models.py`** (if needed)
   - Verify `wikimedia_username` field exists
   - Add `original_sso_username` field if needed

## Testing Plan

### Manual Testing Steps
1. Clear database or use fresh user
2. Attempt MediaWiki OAuth login
3. Check logs for username extraction
4. Verify `wikimedia_username` in database
5. Verify username appears in UI where expected

### Automated Testing
1. Unit tests for signal handler
2. Integration tests for OAuth flow
3. Test data extraction from mock extra_data

## Success Criteria
- ✅ `wikimedia_username` field is populated after OAuth login
- ✅ Username persists across sessions
- ✅ Username updates if changed on MediaWiki
- ✅ Clear logging shows username extraction process
- ✅ Works for both new and existing users

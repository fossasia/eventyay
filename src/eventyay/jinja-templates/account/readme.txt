This folder contains template override for django-allauth views, which are registered URL in "/account/".

Customized Templates:
======================

1. email_confirm.jinja
   - Customized email confirmation page displayed when users click the email verification link
   - Rendered via ConfirmEmailView (eventyay_common.views.custom.ConfirmEmailView) with explicit template_name
   - Updated links to point to eventyay_common views (e.g., dashboard, email management)
   - Styled with Eventyay's primary color (#2185d0) and theme
   - Uses Font Awesome icons for improved user experience
   - Fully responsive design for mobile and desktop devices
   - Provides clear messaging for confirmation success, errors, and expired links
   - Message strings are built in Python to keep translations free of HTML; template consumes
     variables like confirmation_message, already_confirmed_message, invalid_confirmation_message

2. password_reset_from_key.jinja
   - Password reset page displayed when users click the password reset link from email
   - Rendered via PasswordResetFromKeyView with conditional logic:
     * Displays form for valid reset tokens
     * Shows warning and action buttons for invalid/expired tokens
   - Uses shared CSS styling from allauth.css
   - Provides clear messaging for form errors and validation help text
   - Includes responsive button layout with fallback to login

3. password_reset_from_key_done.jinja
   - Success page displayed after password has been successfully reset
   - Shows success icon and confirmation message
   - Provides links to log in or return to dashboard
   - Uses shared CSS styling from allauth.css
   - Fully responsive design with centered layout

4. base.jinja
   - Base template for account pages
   - Provides consistent layout and styling across account flows
   - Includes Eventyay branding colors (#2185d0 theme color)
   - Minimal, focused design to keep users on task
   - Integrated CSS styling for alerts, buttons, and forms
   - Loads Font Awesome icons locally (relative paths for CSP compliance)

Shared Styling:
===============
- allauth.css
  * Shared stylesheet for password reset/change templates
  * Contains form styling, buttons, alerts, and responsive design rules
  * Used by password_reset_from_key.jinja and password_reset_from_key_done.jinja

Configuration:
==============
- View overrides:
  * ConfirmEmailView lives in eventyay_common/views/custom.py and is an override of django-allauth to build messages in a safe way: not leak HTML code to translatable strings.
  * PasswordResetFromKeyView and PasswordResetFromKeyDoneView use built-in django-allauth views.
  * Root URL override: /accounts/confirm-email/<key>/ is registered with name `account_confirm_email`
    in config/urls.py before including allauth, so allauth-generated links resolve to our view.

- Email confirmation redirects:
  * ACCOUNT_EMAIL_CONFIRMATION_AUTHENTICATED_REDIRECT_URL is set to '/common/account/email'
    to redirect logged-in users to their email management page after confirming additional emails
  * This provides optimal UX for authenticated users (managing multiple emails)

- Icon fonts:
  * Alert icons use Font Awesome icon codes (\f00c, \f05a, \f071)
  * Font files are served locally from static/fontawesome/fonts/ with relative paths
  * CSS font-family set to "FontAwesome" for proper icon rendering
  * All fonts loaded locally to comply with Content Security Policy

This folder contains template override for django-allauth views, which are registered URL in "/account/".

Customized Templates:
======================

1. email_confirm.jinja
   - Customized email confirmation page displayed when users click the email verification link
   - Updated links to point to eventyay_common views (e.g., dashboard, email management)
   - Styled with Eventyay's primary color (#2185d0) and theme
   - Uses Font Awesome icons for improved user experience
   - Fully responsive design for mobile and desktop devices
   - Provides clear messaging for confirmation success, errors, and expired links

2. email_confirm_success.jinja
   - Post-confirmation success page displayed after email is verified
   - Dynamically adjusts content based on authentication state:
     * Authenticated users: Links to manage email addresses and return to dashboard
     * Anonymous users: Prompts to log in with the confirmed email
   - Uses same styling and branding as other account pages
   - Extends base_entrance.jinja for consistency

3. base_entrance.jinja
   - Base template for account-related entrance pages (login, signup, confirmations, etc.)
   - Provides consistent layout and styling across all auth flows
   - Includes Eventyay branding colors (#2185d0 theme color)
   - Minimal, focused design to keep users on task
   - Integrated CSS styling for alerts, buttons, and forms

Configuration:
==============
- Email confirmation redirects:
  * ACCOUNT_EMAIL_CONFIRMATION_AUTHENTICATED_REDIRECT_URL is set to '/common/account/email'
    to redirect logged-in users to their email management page after confirming additional emails
  * Anonymous users use the template-based flow with email_confirm_success.jinja
  * This provides optimal UX for both authenticated (managing multiple emails) and
    anonymous users (first-time email verification)

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
   - Extends base.jinja for consistency

3. base.jinja
   - Base template for email confirmation pages
   - Provides consistent layout and styling across email confirmation flows
   - Includes Eventyay branding colors (#2185d0 theme color)
   - Minimal, focused design to keep users on task
   - Integrated CSS styling for alerts, buttons, and forms
   - Loads Font Awesome icons locally (relative paths for CSP compliance)

Configuration:
==============
- Email confirmation redirects:
  * ACCOUNT_EMAIL_CONFIRMATION_AUTHENTICATED_REDIRECT_URL is set to '/common/account/email'
    to redirect logged-in users to their email management page after confirming additional emails
  * Anonymous users use the template-based flow with email_confirm_success.jinja
  * This provides optimal UX for both authenticated (managing multiple emails) and
    anonymous users (first-time email verification)

- Icon fonts:
  * Alert icons use Font Awesome icon codes (\f00c, \f05a, \f071)
  * Font files are served locally from static/fontawesome/fonts/ with relative paths
  * CSS font-family set to "FontAwesome" for proper icon rendering
  * All fonts loaded locally to comply with Content Security Policy

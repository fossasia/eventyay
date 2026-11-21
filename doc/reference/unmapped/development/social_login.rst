:orphan:

Social Login Setup
--------------------------

To enable social login for providers, you first need to create an OAuth application on the provider's website.


I. Google OAuth Application
----------------------------
Create an OAuth application on https://console.developers.google.com/

Instructions:

- Follow the setup guide: https://medium.com/@tony.infisical/guide-to-using-oauth-2-0-to-access-google-apis-dead94d6866d

- Set the callback URL to: `{domain}/accounts/google/login/callback/`

- Add the client ID and client secret to admin settings


II. Github OAuth Application
-----------------------------
Create an OAuth application on https://github.com/settings/applications/new

Instructions:

- Set the callback URL to: `{domain}/accounts/github/login/callback/`

- Add the client ID and client secret to admin settings


III. MediaWiki OAuth Application
---------------------------------
To enable MediaWiki social login for your eventyay instance, you need to register an OAuth application with MediaWiki.

Important Notes
~~~~~~~~~~~~~~~~

- The OAuth application must be approved by a MediaWiki administrator

- Until approved, only the application owner can log in

Registration Steps
~~~~~~~~~~~~~~~~~~~

1. Register your OAuth application at: 
   https://meta.wikimedia.org/wiki/Special:OAuthConsumerRegistration/propose

2. Callback URL Configuration

   - Set the OAuth "callback" URL to: `{domain}/accounts/mediawiki/login/callback/`

   - Example: `http://localhost:8000/accounts/mediawiki/login/callback/`
   
3. Carefully read and follow the instructions on the registration page. Tick option: access private information.

4. The registered application will return:

   - One consumer key

   - One consumer secret

5. Add the consumer key and consumer secret to your eventyay admin settings

After Approval
~~~~~~~~~~~~~~~
Once approved, other users can log in to your eventyay instance using their MediaWiki account.


IV. Generic OpenID Connect (OIDC)
---------------------------------

Eventyay supports OIDC-compatible identity providers (such as Keycloak) through
Django Allauth's generic OpenID Connect provider.

1. Set ``EVY_OIDC_ISSUER_URL`` to the provider's OIDC issuer URL, for example
   ``https://id.example.org/realms/example``.
2. Optionally set ``EVY_OIDC_PROVIDER_NAME`` to customize the login-button
   label (defaults to ``OpenID Connect``).
3. Register an OIDC client with the identity provider, allowing this callback:
   ``https://your-eventyay-domain/accounts/oidc/openid_connect/login/callback/``
4. Under Eventyay's admin **Social login settings**, enable **Openid_connect**,
   enter the client ID and secret, and save. Optionally make it the preferred
   login method.

Disabling the provider removes its Allauth configuration and blocks new OIDC
logins. Native password login and other configured providers remain available.

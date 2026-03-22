from django.conf import settings

mf_settings = getattr(settings, 'MULTIFACTOR', {})

mf_settings['LOGIN_MESSAGE'] = mf_settings.get('LOGIN_MESSAGE', 'You are now multifactor-authenticated. <a href="{}">Multifactor settings</a>.')
mf_settings['SHOW_LOGIN_MESSAGE'] = mf_settings.get('SHOW_LOGIN_MESSAGE', True)
mf_settings['LOGIN_CALLBACK'] = mf_settings.get('LOGIN_CALLBACK', False)
mf_settings['RECHECK'] = mf_settings.get('RECHECK', True)
mf_settings['RECHECK_MIN'] = mf_settings.get('RECHECK_MIN', 60 * 60 * 3)
mf_settings['RECHECK_MAX'] = mf_settings.get('RECHECK_MAX', 60 * 60 * 6)

mf_settings['FIDO_SERVER_ID'] = mf_settings.get('FIDO_SERVER_ID', 'example.com')
mf_settings['FIDO_SERVER_NAME'] = mf_settings.get('FIDO_SERVER_NAME', 'Django App')
mf_settings['FIDO_SERVER_ICON'] = mf_settings.get('FIDO_SERVER_ICON', None)
mf_settings['TOKEN_ISSUER_NAME'] = mf_settings.get('TOKEN_ISSUER_NAME', 'Django App')

mf_settings['FACTORS'] = mf_settings.get('FACTORS', ['FIDO2', 'TOTP'])

mf_settings['FALLBACKS'] = mf_settings.get('FALLBACKS', {
    'email': (lambda user: user.email, 'multifactor.factors.fallback.send_email'),
})

mf_settings['HTML_EMAIL'] = mf_settings.get('HTML_EMAIL', True)

mf_settings['BYPASS'] = mf_settings.get('BYPASS', None)
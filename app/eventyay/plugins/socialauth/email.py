from allauth.account.models import EmailAddress


def ensure_verified_email_for_user(user, email: str | None) -> None:
    if not user:
        return
    resolved_email = (email or user.email or '').lower()
    if not resolved_email:
        return
    email_address = EmailAddress.objects.filter(user=user, email__iexact=resolved_email).order_by('pk').first()
    if email_address is None:
        EmailAddress.objects.create(
            user=user,
            email=resolved_email,
            verified=True,
            primary=False,
        )
        return

    update_fields: list[str] = []
    if email_address.email != resolved_email:
        email_address.email = resolved_email
        update_fields.append('email')
    if not email_address.verified:
        email_address.verified = True
        update_fields.append('verified')
    if update_fields:
        email_address.save(update_fields=update_fields)


def get_verified_mediawiki_sociallogin_email(sociallogin) -> str | None:
    for address in sociallogin.email_addresses:
        if address.email and address.verified:
            return address.email

    extra_data = sociallogin.account.extra_data or {}
    extra_email = extra_data.get('email')
    if isinstance(extra_email, str) and extra_email and extra_data.get('confirmed_email') is True:
        return extra_email

    if sociallogin.is_existing and sociallogin.user and sociallogin.user.email:
        return sociallogin.user.email
    return None

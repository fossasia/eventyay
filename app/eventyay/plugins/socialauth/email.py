from allauth.account.models import EmailAddress


def ensure_verified_email_for_user(user, email: str | None) -> None:
    if not user:
        return
    resolved_email = (email or user.email or '').lower()
    if not resolved_email:
        return
    email_address, created = EmailAddress.objects.get_or_create(
        user=user,
        email=resolved_email,
        defaults={'verified': True, 'primary': False},
    )
    if not created and not email_address.verified:
        email_address.verified = True
        email_address.save(update_fields=['verified'])

def is_wikimedia_user(user):
    """
    Check if user is authenticated via Wikimedia OAuth

    Args:
        user: Django User instance

    Returns:
        bool: True if user is a Wikimedia OAuth user
    """
    return user.is_authenticated and getattr(user, 'is_wikimedia_user', False)

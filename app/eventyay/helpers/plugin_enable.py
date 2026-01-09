def is_video_enabled(event):
    """
    Check if video is configured/enabled.
    @param event: event object
    @return: boolean
    """
    if (
        not event.settings.venueless_url
        or not event.settings.venueless_issuer
        or not event.settings.venueless_audience
        or not event.settings.venueless_secret
    ):
        return False
    return True

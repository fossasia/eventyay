"""Redirect views for backward compatibility with legacy URLs."""

from django.http import HttpResponsePermanentRedirect, Http404
from django.shortcuts import get_object_or_404
from eventyay.base.models import Event


def legacy_video_redirect(request, event_identifier):
    """
    Redirect legacy video URLs from /video/<event_identifier> to /{organizer}/{event}/video.
    
    Args:
        request: The HTTP request
        event_identifier: Can be either event.pk or event.slug
    
    Returns:
        HttpResponsePermanentRedirect to new URL structure
    """
    # Try to find event by PK first, then by slug
    event = None
    try:
        if event_identifier.isdigit():
            event = Event.objects.select_related('organizer').get(pk=int(event_identifier))
        else:
            event = Event.objects.select_related('organizer').get(slug=event_identifier)
    except Event.DoesNotExist as exc:
        raise Http404("Event not found") from exc
    
    # Preserve the path after the event identifier
    path_parts = request.path.split('/', 3)
    remaining_path = path_parts[3] if len(path_parts) > 3 else ''
    
    # Build new URL: /{organizer}/{event}/video/{remaining_path}
    new_url = f"/{event.organizer.slug}/{event.slug}/video/"
    if remaining_path:
        new_url += remaining_path
    
    # Preserve query string
    if request.GET:
        new_url += f'?{request.GET.urlencode()}'
    
    return HttpResponsePermanentRedirect(new_url)


def legacy_talk_redirect(request, event_slug):
    """
    Redirect legacy talk URLs from /<event>/* to /{organizer}/{event}/*.
    
    This handles URLs like:
    - /<event>/schedule -> /{organizer}/{event}/schedule
    - /<event>/talk/<slug> -> /{organizer}/{event}/talk/<slug>
    - /<event>/cfp -> /{organizer}/{event}/cfp
    
    Args:
        request: The HTTP request
        event_slug: The event slug from the URL
    
    Returns:
        HttpResponsePermanentRedirect to new URL structure
    """
    # Find event by slug (need to get organizer)
    event = get_object_or_404(Event.objects.select_related('organizer'), slug=event_slug)
    
    # Get the full path after the event slug
    path_parts = request.path.split('/', 2)
    remaining_path = path_parts[2] if len(path_parts) > 2 else ''
    
    # Build new URL: /{organizer}/{event}/{remaining_path}
    new_url = f"/{event.organizer.slug}/{event.slug}/"
    if remaining_path:
        new_url += remaining_path
    
    # Preserve query string
    if request.GET:
        new_url += f'?{request.GET.urlencode()}'
    
    return HttpResponsePermanentRedirect(new_url)


"""Legacy eventyay-talk integration tasks.

This module previously contained a Celery task to configure an external talk system
and store connection metadata in ``event.config['pretalx']`` (domain/event/connected/pushed).

The video SPA now connects directly, so the legacy integration was removed.
"""

# Intentionally left empty.

import logging

from django.apps import AppConfig
from django.db.models.signals import post_migrate

logger = logging.getLogger(__name__)


def sync_existing_talk_only_teams(sender, **kwargs):
    """
    Automatically sync events to existing Talk-only teams after migrations.
    
    This ensures that existing Talk-only teams created before this implementation
    get their events synced automatically during deployment, without requiring
    manual script execution.
    
    This runs automatically after migrations complete, ensuring all existing
    Talk-only teams have events in their limit_events so they appear in dashboards.
    """
    # Only run if migrations are complete and database is ready
    try:
        from django.db import connection
        from django.core.management import get_commands
        
        # Check if database is ready
        connection.ensure_connection()
        
        # Only sync if we're not in a management command that might conflict
        # (e.g., during migrations, collectstatic, etc.)
        import sys
        if len(sys.argv) > 1:
            command = sys.argv[1]
            # Skip syncing during certain commands to avoid conflicts
            skip_commands = ['migrate', 'makemigrations', 'collectstatic', 'test', 'shell']
            if command in skip_commands:
                return
        
        from eventyay.base.services.team_event_sync import sync_all_talk_only_teams
        
        # Sync all Talk-only teams automatically
        results = sync_all_talk_only_teams()
        
        if results['teams_synced'] > 0:
            logger.info(
                f"Automatically synced {results['teams_synced']} Talk-only team(s), "
                f"added {results['events_added']} event(s) total"
            )
        elif results['teams_processed'] > 0:
            logger.debug(
                f"Checked {results['teams_processed']} team(s) - all Talk-only teams already synced"
            )
    except Exception as e:
        # Log error but don't fail startup if syncing fails
        # This ensures the app can start even if syncing encounters issues
        logger.warning(f"Failed to sync Talk-only teams automatically: {e}", exc_info=True)


class EventyayBaseConfig(AppConfig):
    name = 'eventyay.base'
    label = 'base'

    def ready(self):
        from . import exporter  # NOQA
        from . import payment  # NOQA
        from . import exporters  # NOQA
        from . import invoice  # NOQA
        from . import notifications  # NOQA
        from . import email  # NOQA
        from django.conf import settings

        try:
            from eventyay.celery_app import app as celery_app  # NOQA
        except ImportError:
            pass

        if hasattr(settings, 'RAVEN_CONFIG'):
            from eventyay.config.sentry import initialize

            initialize()
        
        # Connect post_migrate signal to automatically sync existing Talk-only teams
        # This runs automatically after migrations complete, ensuring existing teams
        # are synced without manual script execution
        post_migrate.connect(sync_existing_talk_only_teams, sender=self)


default_app_config = 'eventyay.base.EventyayBaseConfig'
try:
    import eventyay.celery_app as celery  # NOQA
except ImportError:
    pass

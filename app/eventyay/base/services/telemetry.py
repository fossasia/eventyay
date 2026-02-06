"""
Telemetry service for sending anonymous usage data from Eventyay instances.

This module implements a daily heartbeat that sends aggregated, anonymous
telemetry data to a central endpoint for tracking deployment statistics,
version adoption, and usage patterns.

Based on the pattern established in update_check.py.
"""
import hashlib
import logging
import os
import platform
import sys
from datetime import timedelta
from urllib.parse import quote

import requests
from django.conf import settings
from django.db import DatabaseError, connection
from django.dispatch import receiver
from django.utils.timezone import now
from django_scopes import scopes_disabled

from eventyay import __version__
from eventyay.base.models import Event, Order, OrderPosition, Organizer
from eventyay.base.models.submission import Submission
from eventyay.base.plugins import get_all_plugins
from eventyay.base.settings import GlobalSettingsObject
from eventyay.base.signals import periodic_task
from eventyay.celery_app import app

logger = logging.getLogger(__name__)


def get_count_bucket(count: int) -> str:
    """
    Convert a numeric count into a privacy-preserving bucket string.
    
    Examples:
        0 -> "0"
        5 -> "1-10"
        75 -> "51-100"
        10000 -> "5000+"
    """
    if count == 0:
        return "0"
    
    # Buckets: 1-10, 11-50, 51-100, 101-500, 501-1000, 1001-5000, 5000+
    bucket_ranges = [
        (1, 10),
        (11, 50),
        (51, 100),
        (101, 500),
        (501, 1000),
        (1001, 5000),
    ]
    
    for low, high in bucket_ranges:
        if count <= high:
            return f"{low}-{high}"
    
    return "5000+"


def get_database_info() -> tuple:
    """
    Get database type and major version.
    
    Returns:
        Tuple of (database_type, database_version)
    """
    db_engine = settings.DATABASES.get('default', {}).get('ENGINE', '')
    
    if 'postgresql' in db_engine or 'psycopg' in db_engine:
        db_type = 'postgresql'
    elif 'mysql' in db_engine:
        db_type = 'mysql'
    elif 'sqlite' in db_engine:
        db_type = 'sqlite'
    else:
        db_type = 'unknown'
    
    # Try to get version from database
    db_version = 'unknown'
    try:
        with connection.cursor() as cursor:
            if db_type == 'postgresql':
                cursor.execute("SELECT version();")
                result = cursor.fetchone()
                if result:
                    # Extract major version from "PostgreSQL 15.3 ..."
                    parts = result[0].split()
                    if len(parts) >= 2:
                        db_version = parts[1].split('.')[0]
            elif db_type == 'mysql':
                cursor.execute("SELECT VERSION();")
                result = cursor.fetchone()
                if result:
                    db_version = result[0].split('.')[0]
            elif db_type == 'sqlite':
                cursor.execute("SELECT sqlite_version();")
                result = cursor.fetchone()
                if result:
                    db_version = result[0].split('.')[0]
    except DatabaseError as e:
        logger.debug("Could not fetch database version: %s", e)
    
    return db_type, db_version


def get_deployment_type() -> str:
    """
    Attempt to detect the deployment type.
    
    Returns:
        One of: 'docker', 'kubernetes', 'native', 'unknown'
    """
    # Check for Docker
    if os.path.exists('/.dockerenv'):
        return 'docker'
    
    # Check for Kubernetes
    if os.environ.get('KUBERNETES_SERVICE_HOST'):
        return 'kubernetes'
    
    # Check for common Docker/container indicators
    try:
        with open('/proc/1/cgroup', 'r') as f:
            if 'docker' in f.read():
                return 'docker'
    except (FileNotFoundError, PermissionError, OSError):
        # Cannot read /proc/1/cgroup, assume not in a container
        pass
    
    return 'native'


def get_storage_backend() -> str:
    """
    Detect the configured storage backend.
    
    Returns:
        One of: 'file', 's3', 'gcs', 'azure', 'unknown'
    """
    storage_backend = getattr(settings, 'DEFAULT_FILE_STORAGE', '')
    
    if 's3' in storage_backend.lower() or 'boto' in storage_backend.lower():
        return 's3'
    elif 'gcs' in storage_backend.lower() or 'google' in storage_backend.lower():
        return 'gcs'
    elif 'azure' in storage_backend.lower():
        return 'azure'
    elif 'FileSystem' in storage_backend or not storage_backend:
        return 'file'
    
    return 'unknown'


@scopes_disabled()
def collect_telemetry_payload() -> dict:
    """
    Collect all telemetry data into a structured payload.
    
    All counts are bucketed for privacy. No PII is collected.
    
    Returns:
        Dictionary containing telemetry payload
    """
    gs = GlobalSettingsObject()
    
    # Get instance identifier
    # Note: Import inside function to avoid circular import with models.settings
    try:
        from eventyay.base.models.settings import GlobalSettings
        instance_id = str(GlobalSettings().get_instance_identifier())
    except (ImportError, AttributeError, TypeError) as e:
        logger.debug("Could not get instance identifier: %s", e)
        instance_id = 'unknown'
    
    # Get database info
    db_type, db_version = get_database_info()
    
    # Get canonical base URL (hashed for privacy)
    base_url = getattr(settings, 'SITE_URL', '') or ''
    base_url_hash = hashlib.sha256(base_url.encode()).hexdigest()[:16] if base_url else ''
    
    # Collect model counts
    try:
        event_count = Event.objects.count()
        live_event_count = Event.objects.filter(live=True).count()
    except DatabaseError as e:
        logger.debug("Could not count events: %s", e)
        event_count = 0
        live_event_count = 0
    
    try:
        organizer_count = Organizer.objects.count()
    except DatabaseError as e:
        logger.debug("Could not count organizers: %s", e)
        organizer_count = 0
    
    try:
        order_count = Order.objects.count()
        paid_order_count = Order.objects.filter(status='p').count()
    except DatabaseError as e:
        logger.debug("Could not count orders: %s", e)
        order_count = 0
        paid_order_count = 0
    
    try:
        submission_count = Submission.objects.count()
    except DatabaseError as e:
        logger.debug("Could not count submissions: %s", e)
        submission_count = 0
    
    # Count attendees (order positions / tickets)
    try:
        total_tickets = OrderPosition.objects.count()
        paid_tickets = OrderPosition.objects.filter(order__status='p').count()
        free_tickets = OrderPosition.objects.filter(price=0).count()
    except DatabaseError as e:
        logger.debug("Could not count tickets: %s", e)
        total_tickets = 0
        paid_tickets = 0
        free_tickets = 0
    
    # Get enabled plugins
    try:
        enabled_plugins = [p.module for p in get_all_plugins() if p.module]
    except (ImportError, AttributeError) as e:
        logger.debug("Could not get plugins: %s", e)
        enabled_plugins = []
    
    # Get uptime info (if available)
    # Note: psutil is an optional dependency
    uptime_seconds = 0
    try:
        import psutil
        boot_time = psutil.boot_time()
        uptime_seconds = int(now().timestamp() - boot_time)
    except (ImportError, OSError, AttributeError) as e:
        logger.debug("Could not get uptime: %s", e)
    
    # Uptime bucket (in hours)
    uptime_hours = uptime_seconds // 3600
    if uptime_hours == 0:
        uptime_bucket = '0-1h'
    elif uptime_hours < 24:
        uptime_bucket = '1-24h'
    elif uptime_hours < 168:  # 7 days
        uptime_bucket = '1-7d'
    elif uptime_hours < 720:  # 30 days
        uptime_bucket = '7-30d'
    else:
        uptime_bucket = '30d+'
    
    # Build metadata from git (optional dependency)
    build_metadata = f"v{__version__}"
    try:
        import git
        try:
            repo = git.Repo(search_parent_directories=True)
            git_commit = repo.head.commit.hexsha[:8]
            # Handle detached HEAD state where active_branch may not exist
            try:
                git_branch = repo.active_branch.name
            except TypeError:
                # Detached HEAD state - use commit hash instead
                git_branch = 'detached'
            build_metadata = f"{git_branch}@{git_commit}"
        except (git.InvalidGitRepositoryError, git.GitCommandNotFound, TypeError, AttributeError) as e:
            logger.debug("Could not get git info: %s", e)
    except ImportError:
        # git module not installed, use version-based metadata
        pass
    
    # Get optional contact email
    contact_email = gs.settings.get('telemetry_contact_email') or ''
    
    # Build payload with all required columns
    payload = {
        'schema_version': '1',
        'instance_id': instance_id,
        'timestamp_utc': now().isoformat(),
        
        # Version info
        'eventyay_version': __version__,
        'build_metadata': build_metadata,
        'python_version': f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        
        # Environment info
        'canonical_base_url_hash': base_url_hash,
        'os_family': platform.system(),
        'os_version': platform.release(),
        'database_type': db_type,
        'database_version': db_version,
        'deployment_type': get_deployment_type(),
        'storage_backend': get_storage_backend(),
        
        # Feature flags
        'celery_enabled': getattr(settings, 'HAS_CELERY', False),
        'redis_enabled': getattr(settings, 'HAS_REDIS', False),
        'background_jobs_enabled': getattr(settings, 'HAS_CELERY', False),
        
        # Bucketed metrics (privacy-preserving)
        'metrics': {
            'events_bucket': get_count_bucket(event_count),
            'live_events_bucket': get_count_bucket(live_event_count),
            'organizers_bucket': get_count_bucket(organizer_count),
            'orders_bucket': get_count_bucket(order_count),
            'paid_orders_bucket': get_count_bucket(paid_order_count),
            'submissions_bucket': get_count_bucket(submission_count),
            'attendees_bucket': get_count_bucket(total_tickets),
            'tickets_issued_bucket': get_count_bucket(total_tickets),
            'paid_tickets_bucket': get_count_bucket(paid_tickets),
            'free_tickets_bucket': get_count_bucket(free_tickets),
            'uptime_bucket': uptime_bucket,
            'error_count_bucket': '0',  # Placeholder - can be enhanced later
        },
        
        # Plugin info
        'enabled_plugins': enabled_plugins,
        
        # Contact info (always included for consistent column count)
        'maintainer_contact': contact_email,
    }
    
    return payload


@receiver(signal=periodic_task)
def run_telemetry(sender, **kwargs):
    """
    Periodic task receiver that triggers telemetry sending.
    
    Runs approximately once per day. Checks if telemetry is enabled
    and if enough time has passed since the last send.
    """
    gs = GlobalSettingsObject()
    
    # Check if telemetry is enabled
    if not gs.settings.get('telemetry_enabled', False):
        return
    
    # Check if we've sent recently (within 23 hours)
    last_sent = gs.settings.get('telemetry_last_sent')
    if last_sent and now() - last_sent < timedelta(hours=23):
        return
    
    # Trigger async telemetry send
    send_telemetry.apply_async()


@app.task(bind=True)
@scopes_disabled()
def send_telemetry(self):
    """
    Celery task to collect and send telemetry data.
    
    Collects telemetry payload and sends it to the configured endpoint.
    Handles failures gracefully and updates last_sent timestamp on success.
    """
    gs = GlobalSettingsObject()
    
    # Double-check telemetry is still enabled
    # Handle both boolean and string values from hierarkey
    telemetry_enabled = gs.settings.telemetry_enabled
    if isinstance(telemetry_enabled, str):
        telemetry_enabled = telemetry_enabled.lower() == 'true'
    if not telemetry_enabled:
        return {'status': 'disabled'}
    
    # Get endpoint configuration (use attribute access for hierarkey)
    endpoint = gs.settings.telemetry_endpoint or None
    api_key = gs.settings.telemetry_api_key or None
    
    if not endpoint:
        # Use default endpoint if not configured
        endpoint = getattr(settings, 'TELEMETRY_DEFAULT_ENDPOINT', None)
    
    if not endpoint:
        # No endpoint configured - update last_sent to prevent queue spam
        gs.settings.set('telemetry_last_sent', now())
        return {'status': 'no_endpoint'}
    
    # Skip in development mode
    if 'runserver' in sys.argv:
        gs.settings.set('telemetry_last_sent', now())
        return {'status': 'development'}
    
    try:
        # Collect payload
        payload = collect_telemetry_payload()
        
        # Prepare headers - include X-API-Key for security
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': f'Eventyay/{__version__}',
        }
        if api_key:
            headers['X-API-Key'] = api_key
        
        # Build request URL.
        # For most endpoints we rely solely on the X-API-Key header. However,
        # Google Apps Script loses custom headers during its internal redirects,
        # so for its HTTPS endpoints we also include the API key as a URL
        # parameter as a compatibility fallback.
        request_url = endpoint
        if api_key and endpoint.startswith('https://script.google.com'):
            separator = '&' if '?' in endpoint else '?'
            request_url = f"{endpoint}{separator}api_key={quote(api_key, safe='')}"
        
        # Send telemetry
        response = requests.post(
            request_url,
            json=payload,
            headers=headers,
            timeout=30,
        )
        
        if response.status_code == 200:
            # Google Apps Script always returns 200, so parse JSON body for actual status
            try:
                response_data = response.json()
                if response_data.get('ok', False):
                    # Only update timestamp on actual success
                    gs.settings.set('telemetry_last_sent', now())
                    return {'status': 'success'}
                else:
                    # Server returned error in JSON body (auth failed, rate limited, etc)
                    error_type = response_data.get('error', 'unknown')
                    return {'status': 'error', 'error_type': error_type}
            except ValueError:
                # Non-JSON response - treat as error
                logger.warning('Telemetry response is not valid JSON')
                return {'status': 'error', 'error_type': 'invalid_json'}
        else:
            # Non-200 status code - don't update timestamp, allow retry
            return {'status': 'error', 'code': response.status_code}
            
    except requests.RequestException as e:
        # Network errors, timeouts, etc. - don't update timestamp, allow retry
        logger.warning("Telemetry request failed: %s", e)
        return {'status': 'error', 'error_type': type(e).__name__}
    except (TypeError, ValueError) as e:
        # JSON serialization errors - log and mark as sent to avoid repeated failures
        logger.warning("Telemetry payload error: %s", e)
        gs.settings.set('telemetry_last_sent', now())
        return {'status': 'error', 'error_type': type(e).__name__}


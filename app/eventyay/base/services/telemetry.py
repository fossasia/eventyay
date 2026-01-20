"""
Telemetry service for sending anonymous usage data from Eventyay instances.

This module implements a daily heartbeat that sends aggregated, anonymous
telemetry data to a central endpoint for tracking deployment statistics,
version adoption, and usage patterns.

Based on the pattern established in update_check.py.
"""
import platform
import sys
from datetime import timedelta

import requests
from django.conf import settings
from django.db import connection
from django.dispatch import receiver
from django.utils.timezone import now
from django_scopes import scopes_disabled

from eventyay import __version__
from eventyay.base.models import Event, Order, Organizer
from eventyay.base.models.submission import Submission
from eventyay.base.plugins import get_all_plugins
from eventyay.base.settings import GlobalSettingsObject
from eventyay.base.signals import periodic_task
from eventyay.celery_app import app


# Bucket thresholds for privacy-preserving count reporting
COUNT_BUCKETS = [0, 1, 10, 50, 100, 500, 1000, 5000]


def get_count_bucket(count: int) -> str:
    """
    Convert a numeric count into a privacy-preserving bucket string.
    
    Examples:
        0 -> "0"
        5 -> "1-10"
        75 -> "50-100"
        10000 -> "5000+"
    """
    if count == 0:
        return "0"
    
    for i, threshold in enumerate(COUNT_BUCKETS[1:], 1):
        if count <= threshold:
            return f"{COUNT_BUCKETS[i-1]+1 if COUNT_BUCKETS[i-1] > 0 else 1}-{threshold}"
    
    return f"{COUNT_BUCKETS[-1]}+"


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
    except Exception:
        pass
    
    return db_type, db_version


def get_deployment_type() -> str:
    """
    Attempt to detect the deployment type.
    
    Returns:
        One of: 'docker', 'kubernetes', 'native', 'unknown'
    """
    import os
    
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
    except (FileNotFoundError, PermissionError):
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
    try:
        from eventyay.base.models.settings import GlobalSettings
        instance_id = str(GlobalSettings().get_instance_identifier())
    except Exception:
        instance_id = 'unknown'
    
    # Get database info
    db_type, db_version = get_database_info()
    
    # Collect model counts
    try:
        event_count = Event.objects.count()
        live_event_count = Event.objects.filter(live=True).count()
    except Exception:
        event_count = 0
        live_event_count = 0
    
    try:
        organizer_count = Organizer.objects.count()
    except Exception:
        organizer_count = 0
    
    try:
        order_count = Order.objects.count()
        paid_order_count = Order.objects.filter(status='p').count()
    except Exception:
        order_count = 0
        paid_order_count = 0
    
    try:
        submission_count = Submission.objects.count()
    except Exception:
        submission_count = 0
    
    # Get enabled plugins
    try:
        enabled_plugins = [p.module for p in get_all_plugins() if p.module]
    except Exception:
        enabled_plugins = []
    
    # Build payload
    payload = {
        'schema_version': '1',
        'instance_id': instance_id,
        'timestamp_utc': now().isoformat(),
        
        # Version info
        'eventyay_version': __version__,
        'python_version': f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        
        # Environment info
        'os_family': platform.system(),
        'os_version': platform.release(),
        'database_type': db_type,
        'database_version': db_version,
        'deployment_type': get_deployment_type(),
        'storage_backend': get_storage_backend(),
        
        # Feature flags
        'celery_enabled': getattr(settings, 'HAS_CELERY', False),
        'redis_enabled': getattr(settings, 'HAS_REDIS', False),
        
        # Bucketed metrics (privacy-preserving)
        'metrics': {
            'events_bucket': get_count_bucket(event_count),
            'live_events_bucket': get_count_bucket(live_event_count),
            'organizers_bucket': get_count_bucket(organizer_count),
            'orders_bucket': get_count_bucket(order_count),
            'paid_orders_bucket': get_count_bucket(paid_order_count),
            'submissions_bucket': get_count_bucket(submission_count),
        },
        
        # Plugin info
        'enabled_plugins': enabled_plugins,
    }
    
    # Optional: Add contact email if configured
    contact_email = gs.settings.get('telemetry_contact_email')
    if contact_email:
        payload['maintainer_contact'] = contact_email
    
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


@app.task(bind=True, max_retries=3)
@scopes_disabled()
def send_telemetry(self):
    """
    Celery task to collect and send telemetry data.
    
    Collects telemetry payload and sends it to the configured endpoint.
    Handles failures gracefully and updates last_sent timestamp on success.
    """
    gs = GlobalSettingsObject()
    
    # Double-check telemetry is still enabled
    if not gs.settings.get('telemetry_enabled', False):
        return {'status': 'disabled'}
    
    # Get endpoint configuration
    endpoint = gs.settings.get('telemetry_endpoint')
    api_key = gs.settings.get('telemetry_api_key')
    
    if not endpoint:
        # Use default endpoint if not configured
        endpoint = getattr(settings, 'TELEMETRY_DEFAULT_ENDPOINT', None)
    
    if not endpoint:
        return {'status': 'no_endpoint'}
    
    # Skip in development mode
    if 'runserver' in sys.argv:
        gs.settings.set('telemetry_last_sent', now())
        return {'status': 'development'}
    
    try:
        # Collect payload
        payload = collect_telemetry_payload()
        
        # Prepare headers
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': f'Eventyay/{__version__}',
        }
        if api_key:
            headers['X-API-Key'] = api_key
        
        # Send telemetry
        response = requests.post(
            endpoint,
            json=payload,
            headers=headers,
            timeout=30,
        )
        
        # Update last sent timestamp
        gs.settings.set('telemetry_last_sent', now())
        
        if response.status_code == 200:
            return {'status': 'success'}
        else:
            return {'status': 'error', 'code': response.status_code}
            
    except requests.RequestException as e:
        gs.settings.set('telemetry_last_sent', now())
        
        # Retry on transient failures
        try:
            self.retry(countdown=3600)  # Retry in 1 hour
        except self.MaxRetriesExceededError:
            pass
        
        return {'status': 'error', 'message': str(e)}
    except Exception as e:
        # Don't let telemetry errors affect the application
        return {'status': 'error', 'message': str(e)}

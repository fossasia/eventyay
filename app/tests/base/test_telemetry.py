"""
Tests for the telemetry service module.
"""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

from django.utils.timezone import now


class TestGetCountBucket:
    """Tests for the count bucketing function."""
    
    def test_zero_bucket(self):
        """Test that 0 returns '0'."""
        from eventyay.base.services.telemetry import get_count_bucket
        assert get_count_bucket(0) == "0"
    
    def test_small_counts(self):
        """Test small count buckets."""
        from eventyay.base.services.telemetry import get_count_bucket
        assert get_count_bucket(1) == "1-10"
        assert get_count_bucket(5) == "1-10"
        assert get_count_bucket(10) == "1-10"
    
    def test_medium_counts(self):
        """Test medium count buckets."""
        from eventyay.base.services.telemetry import get_count_bucket
        assert get_count_bucket(11) == "11-50"
        assert get_count_bucket(50) == "11-50"
        assert get_count_bucket(51) == "51-100"
        assert get_count_bucket(100) == "51-100"
    
    def test_large_counts(self):
        """Test large count buckets."""
        from eventyay.base.services.telemetry import get_count_bucket
        assert get_count_bucket(101) == "101-500"
        assert get_count_bucket(500) == "101-500"
        assert get_count_bucket(501) == "501-1000"
        assert get_count_bucket(1000) == "501-1000"
    
    def test_very_large_counts(self):
        """Test very large count buckets."""
        from eventyay.base.services.telemetry import get_count_bucket
        assert get_count_bucket(1001) == "1001-5000"
        assert get_count_bucket(5000) == "1001-5000"
        assert get_count_bucket(5001) == "5000+"
        assert get_count_bucket(100000) == "5000+"


class TestGetDatabaseInfo:
    """Tests for database info detection."""
    
    @patch('eventyay.base.services.telemetry.settings')
    @patch('eventyay.base.services.telemetry.connection')
    def test_postgresql_detection(self, mock_connection, mock_settings):
        """Test PostgreSQL database detection."""
        mock_settings.DATABASES = {'default': {'ENGINE': 'django.db.backends.postgresql'}}
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = ('PostgreSQL 15.3 on x86_64-pc-linux-gnu',)
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor
        
        from eventyay.base.services.telemetry import get_database_info
        db_type, db_version = get_database_info()
        
        assert db_type == 'postgresql'
        assert db_version == '15'
    
    @patch('eventyay.base.services.telemetry.settings')
    def test_sqlite_detection(self, mock_settings):
        """Test SQLite database detection."""
        mock_settings.DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3'}}
        
        from eventyay.base.services.telemetry import get_database_info
        db_type, _ = get_database_info()
        
        assert db_type == 'sqlite'


class TestGetDeploymentType:
    """Tests for deployment type detection."""
    
    @patch('os.path.exists')
    @patch.dict('os.environ', {}, clear=True)
    def test_native_deployment(self, mock_exists):
        """Test native deployment detection."""
        mock_exists.return_value = False
        
        from eventyay.base.services.telemetry import get_deployment_type
        assert get_deployment_type() == 'native'
    
    @patch('os.path.exists')
    @patch.dict('os.environ', {}, clear=True)
    def test_docker_deployment(self, mock_exists):
        """Test Docker deployment detection."""
        mock_exists.return_value = True  # /.dockerenv exists
        
        from eventyay.base.services.telemetry import get_deployment_type
        assert get_deployment_type() == 'docker'
    
    @patch('os.path.exists')
    @patch.dict('os.environ', {'KUBERNETES_SERVICE_HOST': '10.0.0.1'})
    def test_kubernetes_deployment(self, mock_exists):
        """Test Kubernetes deployment detection."""
        mock_exists.return_value = False
        
        from eventyay.base.services.telemetry import get_deployment_type
        assert get_deployment_type() == 'kubernetes'


class TestGetStorageBackend:
    """Tests for storage backend detection."""
    
    @patch('eventyay.base.services.telemetry.settings')
    def test_s3_storage(self, mock_settings):
        """Test S3 storage detection."""
        mock_settings.DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
        
        from eventyay.base.services.telemetry import get_storage_backend
        assert get_storage_backend() == 's3'
    
    @patch('eventyay.base.services.telemetry.settings')
    def test_gcs_storage(self, mock_settings):
        """Test GCS storage detection."""
        mock_settings.DEFAULT_FILE_STORAGE = 'storages.backends.gcloud.GoogleCloudStorage'
        
        from eventyay.base.services.telemetry import get_storage_backend
        assert get_storage_backend() == 'gcs'
    
    @patch('eventyay.base.services.telemetry.settings')
    def test_file_storage(self, mock_settings):
        """Test file storage detection."""
        mock_settings.DEFAULT_FILE_STORAGE = 'django.core.files.storage.FileSystemStorage'
        
        from eventyay.base.services.telemetry import get_storage_backend
        assert get_storage_backend() == 'file'


class TestCollectTelemetryPayload:
    """Tests for telemetry payload collection."""
    
    @pytest.mark.django_db
    @patch('eventyay.base.services.telemetry.get_database_info')
    @patch('eventyay.base.services.telemetry.get_deployment_type')
    @patch('eventyay.base.services.telemetry.get_storage_backend')
    @patch('eventyay.base.services.telemetry.get_all_plugins')
    def test_payload_structure(
        self, mock_plugins, mock_storage, mock_deployment, mock_db
    ):
        """Test that payload has required structure."""
        mock_db.return_value = ('postgresql', '15')
        mock_deployment.return_value = 'docker'
        mock_storage.return_value = 'file'
        mock_plugins.return_value = []
        
        from eventyay.base.services.telemetry import collect_telemetry_payload
        payload = collect_telemetry_payload()
        
        # Check required fields
        assert 'schema_version' in payload
        assert payload['schema_version'] == '1'
        assert 'instance_id' in payload
        assert 'timestamp_utc' in payload
        assert 'eventyay_version' in payload
        assert 'python_version' in payload
        assert 'metrics' in payload
        
        # Check metrics structure
        metrics = payload['metrics']
        assert 'events_bucket' in metrics
        assert 'orders_bucket' in metrics
        assert 'submissions_bucket' in metrics
    
    @pytest.mark.django_db
    @patch('eventyay.base.services.telemetry.get_database_info')
    @patch('eventyay.base.services.telemetry.get_deployment_type')
    @patch('eventyay.base.services.telemetry.get_storage_backend')
    @patch('eventyay.base.services.telemetry.get_all_plugins')
    def test_payload_privacy(
        self, mock_plugins, mock_storage, mock_deployment, mock_db
    ):
        """Test that payload respects privacy (bucketed counts)."""
        mock_db.return_value = ('postgresql', '15')
        mock_deployment.return_value = 'docker'
        mock_storage.return_value = 'file'
        mock_plugins.return_value = []
        
        from eventyay.base.services.telemetry import collect_telemetry_payload
        payload = collect_telemetry_payload()
        
        # Metrics should be string buckets, not exact numbers
        for key, value in payload['metrics'].items():
            assert isinstance(value, str), f"Metric {key} should be a string bucket"
            # Should match bucket pattern: "0", "X-Y", or "X+"
            assert value == "0" or "-" in value or value.endswith("+")


class TestRunTelemetry:
    """Tests for the periodic task receiver."""
    
    @pytest.mark.django_db
    @patch('eventyay.base.services.telemetry.send_telemetry')
    @patch('eventyay.base.services.telemetry.GlobalSettingsObject')
    def test_disabled_telemetry(self, mock_gs_class, mock_send):
        """Test that disabled telemetry doesn't send."""
        mock_gs = MagicMock()
        mock_gs.settings.get.return_value = False  # telemetry_enabled
        mock_gs_class.return_value = mock_gs
        
        from eventyay.base.services.telemetry import run_telemetry
        run_telemetry(sender=None)
        
        mock_send.apply_async.assert_not_called()
    
    @pytest.mark.django_db
    @patch('eventyay.base.services.telemetry.send_telemetry')
    @patch('eventyay.base.services.telemetry.GlobalSettingsObject')
    @patch('eventyay.base.services.telemetry.now')
    def test_rate_limiting(self, mock_now, mock_gs_class, mock_send):
        """Test that recent sends are rate limited."""
        current_time = datetime(2026, 1, 20, 12, 0, 0)
        mock_now.return_value = current_time
        
        mock_gs = MagicMock()
        mock_gs.settings.get.side_effect = [
            True,  # telemetry_enabled
            current_time - timedelta(hours=12),  # telemetry_last_sent (within 23h)
        ]
        mock_gs_class.return_value = mock_gs
        
        from eventyay.base.services.telemetry import run_telemetry
        run_telemetry(sender=None)
        
        mock_send.apply_async.assert_not_called()
    
    @pytest.mark.django_db
    @patch('eventyay.base.services.telemetry.send_telemetry')
    @patch('eventyay.base.services.telemetry.GlobalSettingsObject')
    @patch('eventyay.base.services.telemetry.now')
    def test_sends_when_due(self, mock_now, mock_gs_class, mock_send):
        """Test that telemetry sends when due."""
        current_time = datetime(2026, 1, 20, 12, 0, 0)
        mock_now.return_value = current_time
        
        mock_gs = MagicMock()
        mock_gs.settings.get.side_effect = [
            True,  # telemetry_enabled
            current_time - timedelta(hours=25),  # telemetry_last_sent (>23h ago)
        ]
        mock_gs_class.return_value = mock_gs
        
        from eventyay.base.services.telemetry import run_telemetry
        run_telemetry(sender=None)
        
        mock_send.apply_async.assert_called_once()

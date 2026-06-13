import ipaddress
import logging
import os
import socket
import urllib.parse
import uuid

import requests
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand
from django.db import transaction

from eventyay.base.models import Event, User, Event_SettingsStore
from eventyay.common.image import validate_image
from eventyay.helpers.image_optimize import optimize_uploaded_image

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = "Imports external images for Events and Users into platform storage."

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Print what would be done without modifying the database.',
        )

    def is_safe_url(self, url):
        try:
            parsed = urllib.parse.urlparse(url)
            if parsed.scheme not in ('http', 'https'):
                self.stderr.write(self.style.ERROR(f"Unsafe scheme in URL: {url}"))
                return False

            hostname = parsed.hostname
            if not hostname:
                self.stderr.write(self.style.ERROR(f"No hostname in URL: {url}"))
                return False

            ip = socket.gethostbyname(hostname)
            ip_obj = ipaddress.ip_address(ip)
            if not ip_obj.is_global:
                self.stderr.write(self.style.ERROR(f"URL resolves to non-global IP ({ip}): {url}"))
                return False
            return True
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Error resolving URL {url}: {e}"))
            return False

    def download_image(self, url):
        if not self.is_safe_url(url):
            return None

        try:
            response = requests.get(url, timeout=10, stream=True)
            response.raise_for_status()

            # Limit size to 10MB
            max_size = 10 * 1024 * 1024
            
            content_length = response.headers.get('Content-Length')
            if content_length and int(content_length) > max_size:
                self.stderr.write(self.style.ERROR(f"Image too large ({content_length} bytes): {url}"))
                return None

            content = b""
            for chunk in response.iter_content(chunk_size=8192):
                content += chunk
                if len(content) > max_size:
                    self.stderr.write(self.style.ERROR(f"Image exceeds size limit during download: {url}"))
                    return None

            return content
        except requests.exceptions.RequestException as e:
            self.stderr.write(self.style.ERROR(f"Failed to download {url}: {e}"))
            return None

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        models_to_check = [
            (Event, 'logo'),
            (Event, 'header_image'),
            (User, 'avatar'),
        ]

        success_count = 0
        failure_count = 0

        # 1. Process Event settings
        keys_to_migrate = ['event_logo_image', 'logo_image']
        settings_qs = Event_SettingsStore.objects.filter(key__in=keys_to_migrate, value__startswith="http")
        if dry_run:
            self.stdout.write(self.style.SUCCESS(f"\n[DRY-RUN] Found {settings_qs.count()} external images in Event Settings."))
            for store in settings_qs:
                self.stdout.write(self.style.SUCCESS(f"[DRY-RUN] Would download and import {store.value} for Event {store.object.slug} ({store.key})"))
        else:
            self.stdout.write(self.style.MIGRATE_HEADING("Processing Event Settings Images"))
            for store in settings_qs:
                url = store.value
                event = store.object
                self.stdout.write(f"Found external URL in Event {event.slug} setting '{store.key}': {url}")
                
                content = self.download_image(url)
                if not content:
                    failure_count += 1
                    continue
                    
                content_file = ContentFile(content)
                try:
                    validate_image(content_file)
                except Exception as e:
                    self.stderr.write(self.style.ERROR(f"Invalid image content from {url}: {e}"))
                    failure_count += 1
                    continue
                    
                try:
                    filename = urllib.parse.urlparse(url).path.split('/')[-1]
                    if not filename:
                        filename = "image.jpg"
                        
                    uploaded = SimpleUploadedFile(filename, content)
                    
                    with transaction.atomic():
                        result = optimize_uploaded_image(uploaded, store.key)
                        
                        uid = uuid.uuid4().hex[:8]
                        base_name = filename.rsplit('.', 1)[0]
                        base_dir = f"pub/{event.organizer.slug}/{event.slug}/img"
                        base_path = f"{base_dir}/{base_name}_{uid}"
                        
                        optimized_name = f"{base_path}.{result.optimized_ext}"
                        optimized_path = default_storage.save(optimized_name, result.optimized)
                        
                        original_name = f"{base_path}_original.{result.original_ext}"
                        default_storage.save(original_name, result.original)
                        
                        event.settings.set(store.key, f"file://{optimized_path}")
                        event.settings.set(f"{store.key}_original_ext", result.original_ext)
                    
                    self.stdout.write(self.style.SUCCESS(f"Successfully imported {url} to {optimized_path}"))
                    success_count += 1
                except Exception as e:
                    self.stderr.write(self.style.ERROR(f"Error saving image from {url}: {e}"))
                    failure_count += 1

        # 2. Process models
        for model_cls, field_name in models_to_check:
            qs = model_cls.objects.filter(**{f"{field_name}__startswith": "http"})
            
            if dry_run:
                self.stdout.write(self.style.SUCCESS(f"\n[DRY-RUN] Found {qs.count()} external images for {model_cls.__name__}.{field_name}."))
                for instance in qs:
                    url = getattr(instance, field_name).name
                    self.stdout.write(self.style.SUCCESS(f"[DRY-RUN] Would download and import {url} on {model_cls.__name__} {instance.pk}"))
                continue

            self.stdout.write(self.style.MIGRATE_HEADING(f"Processing {model_cls.__name__}.{field_name}"))
            
            for instance in qs:
                url = getattr(instance, field_name).name
                self.stdout.write(f"Found external URL on {model_cls.__name__} {instance.pk}: {url}")
                
                content = self.download_image(url)
                if not content:
                    failure_count += 1
                    continue

                content_file = ContentFile(content)
                
                try:
                    validate_image(content_file)
                except Exception as e:
                    self.stderr.write(self.style.ERROR(f"Invalid image content from {url}: {e}"))
                    failure_count += 1
                    continue

                try:
                    filename = urllib.parse.urlparse(url).path.split('/')[-1]
                    if not filename:
                        filename = "image.jpg"
                        
                    with transaction.atomic():
                        field = getattr(instance, field_name)
                        setattr(instance, field_name, '')
                        field.save(filename, content_file, save=False)
                        instance.save(update_fields=[field_name])
                    
                    self.stdout.write(self.style.SUCCESS(f"Successfully imported {url} to {field.name}"))
                    
                    if hasattr(instance, 'process_image'):
                        instance.process_image(field_name, generate_thumbnail=(field_name == 'avatar'))
                        
                    success_count += 1
                except Exception as e:
                    self.stderr.write(self.style.ERROR(f"Error saving image from {url}: {e}"))
                    failure_count += 1

        if not dry_run:
            self.stdout.write(self.style.SUCCESS(f"\nImport finished: {success_count} succeeded, {failure_count} failed."))

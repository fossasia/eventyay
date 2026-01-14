#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eventyay.config.settings')
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

# Create test superuser if it doesn't exist
email = 'test@eventyay.com'
password = 'TestPassword123!'

if not User.objects.filter(email=email).exists():
    user = User.objects.create_superuser(email=email, password=password)
    print(f"✅ Created superuser: {email}")
    print(f"Password: {password}")
else:
    print(f"ℹ️  User {email} already exists")
    # Update password just in case
    user = User.objects.get(email=email)
    user.set_password(password)
    user.save()
    print(f"✅ Updated password for: {email}")

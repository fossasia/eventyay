
import os
import sys

# Set up environment variables to mimic Render
os.environ['django_settings_module'] = 'eventyay.config.settings'
os.environ['EVY_SITE_URL'] = 'https://eventyay-next-web.onrender.com'
os.environ['EVY_RUNNING_ENVIRONMENT'] = 'production'
os.environ['EVY_SECRET_KEY'] = 'debug_secret'
os.environ['EVY_REDIS_URL'] = 'redis://localhost:6379/1'

# Add app to path
sys.path.append(os.path.join(os.getcwd(), 'app'))

try:
    from eventyay.config.settings import SITE_URL, SITE_NETLOC
    print(f"SITE_URL: {SITE_URL}")
    print(f"SITE_NETLOC: {SITE_NETLOC}")
except Exception as e:
    print(f"Error loading settings: {e}")

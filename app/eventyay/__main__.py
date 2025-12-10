import os
import sys

if __name__ == '__main__':
    os.environ.setdefault('EVY_RUNNING_ENVIRONMENT', 'production')
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eventyay.config.next_settings')

    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)

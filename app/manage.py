#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""

import os
import sys


def main():
    """Run administrative tasks."""
    os.environ.setdefault('EVY_RUNNING_ENVIRONMENT', 'development')
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eventyay.config.next_settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            'available on your PYTHONPATH environment variable? Did you '
            'forget to activate a virtual environment?'
        ) from exc
    if len(sys.argv) > 1 and sys.argv[1] == 'runserver':
        import socket
        import re

        # Default port
        port = 8000
        host = '127.0.0.1'

        # Try to parse port/host from arguments
        for arg in sys.argv[2:]:
            if arg.startswith('--noreload'):
                continue
            # Handle [addr:]port format
            if re.match(r'^\d+$', arg):
                port = int(arg)
            elif ':' in arg:
                parts = arg.split(':')
                if parts[-1].isdigit():
                    port = int(parts[-1])
                    host = parts[0] or '127.0.0.1'

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        try:
            result = sock.connect_ex((host, port))
            if result == 0:
                print(f"\n\033[91mError: Port {port} is already in use.\033[0m")
                print(f"It seems another instance of the server is running.")
                print(f"You can try to kill it with the following command:\n")
                print(f"    \033[1mlsof -ti :{port} | xargs kill -9\033[0m\n")
                # We do not exit here, we let Django try and fail, ensuring we don't block
                # valid (but rare) multiple-binding scenarios or race conditions.
                # But giving the hint is what was requested.
        except Exception:
            pass
        finally:
            sock.close()

    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()

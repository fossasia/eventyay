
import os
import sys
import redis
from urllib.parse import urlparse

def test_connection():
    redis_url = os.environ.get("EVY_REDIS_URL")
    print(f"DEBUG: EVY_REDIS_URL is set to: {redis_url}")
    
    if not redis_url:
        print("ERROR: EVY_REDIS_URL is not set!")
        return

    try:
        r = redis.from_url(redis_url, socket_connect_timeout=5)
        print(f"Attempting to ping Redis at {redis_url}...")
        r.ping()
        print("SUCCESS: Connected to Redis!")
    except Exception as e:
        print(f"FAILURE: Could not connect to Redis. Error: {e}")
        # Print network info
        import socket
        try:
            parsed = urlparse(redis_url)
            host = parsed.hostname
            ip = socket.gethostbyname(host)
            print(f"Resolved {host} to {ip}")
        except Exception as dns_e:
            print(f"DNS Resolution failed: {dns_e}")

if __name__ == "__main__":
    test_connection()

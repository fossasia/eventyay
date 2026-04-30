"""
Webhook test receiver for Eventyay chat webhook feature.

Run:  python tools/test_webhook_receiver.py
Then use tools/configure_chat_webhook.py to register this endpoint.

This server:
  1. Responds to challenge verification (GET ?challenge=...)
  2. Receives webhook POSTs and prints them
  3. Verifies HMAC-SHA256 signatures
"""

import hashlib
import hmac
import json
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

HMAC_SECRET = "test-webhook-secret-12345"
PORT = 9999


class WebhookHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        """Handle challenge verification."""
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        challenge = params.get("challenge", [None])[0]

        if challenge:
            response = json.dumps({"challenge": challenge})
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(response.encode())
            print(f"\n[CHALLENGE] Responded to challenge: {challenge[:20]}...")
        else:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Missing challenge parameter")

    def do_POST(self):
        """Handle webhook delivery."""
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        signature_header = self.headers.get("X-Eventyay-Signature", "")

        # Verify HMAC
        expected = hmac.new(
            HMAC_SECRET.encode(), body, hashlib.sha256
        ).hexdigest()
        actual = signature_header.removeprefix("sha256=")
        sig_valid = hmac.compare_digest(expected, actual)

        # Parse payload
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            payload = {"_raw": body.decode(errors="replace")}

        # Print results
        print("\n" + "=" * 60)
        print("[WEBHOOK RECEIVED]")
        print(f"  Signature valid: {'YES' if sig_valid else 'NO'}")
        print(f"  Signature:       {signature_header}")
        print(f"  Payload:")
        print(json.dumps(payload, indent=4))
        print("=" * 60)

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"status": "ok"}')

    def log_message(self, format, *args):
        """Suppress default access logs to keep output clean."""
        pass


def main():
    server = HTTPServer(("0.0.0.0", PORT), WebhookHandler)
    print(f"Webhook test receiver running on http://0.0.0.0:{PORT}")
    print(f"HMAC secret: {HMAC_SECRET}")
    print(f"Waiting for webhook deliveries...")
    print(f"(Press Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.server_close()


if __name__ == "__main__":
    main()

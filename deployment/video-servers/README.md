# Eventyay Video Servers

Standalone Docker Compose deployment for Eventyay video services:
- **Caddy**: Reverse proxy serving HTTPS with TLS termination for video endpoints
- **Janus**: WebRTC signalling and media gateway (VideoRoom, audiobridge, etc.)
- **Coturn**: High-performance STUN/TURN server for WebRTC NAT traversal
- **Jitsi Meet**: Video conferencing stack (Prosody XMPP, Jicofo, JVB, Web UI)

---

## ⚠️ Important: Host Separation Notice

> **DO NOT deploy or run these video services alongside the main Eventyay deployment on the same host or VM.**
>
> - **Port Conflicts**: This stack binds directly to ports `80` and `443` for TLS reverse proxying, conflicting with Eventyay's primary web server/reverse proxy.
> - **Host Networking**: Coturn runs with `network_mode: host` to properly advertise public ICE candidates, requiring exclusive control of TURN port `3478` and UDP relay range `49152-49200`.
> - **Resource Isolation**: WebRTC audio/video encoding and media relay are network and CPU intensive. Running them on a dedicated server prevents media traffic spikes from impacting Eventyay's core ticketing, database, and API operations.

---

## Quick Start

1. **Navigate to the video-servers directory**:
   ```bash
   cd deployment/video-servers
   ```

2. **Create your environment file**:
   ```bash
   cp env.sample .env
   ```

3. **Select active services via profiles**:
   Configure `COMPOSE_PROFILES` in `.env` to start only the service groups you need:
   ```env
   # Start all services:
   COMPOSE_PROFILES=proxy,janus,turn,jitsi

   # Or run only Janus and Coturn (e.g., if using an external Jitsi cluster):
   COMPOSE_PROFILES=janus,turn
   ```

4. **Start the stack**:
   ```bash
   docker compose up -d
   ```

5. **Stop the stack**:
   ```bash
   docker compose down
   ```

---

## Service Profiles

| Profile | Included Services | Default Ports | Description |
|---|---|---|---|
| `proxy` | `caddy` | `80`, `443` | Reverse proxy routing `/janus`, `/janus-ws`, and `/` |
| `janus` | `janus` | `8188`, `8088`, `7088`, `20000-20050/udp` | Janus WebRTC gateway |
| `turn` | `coturn` | `3478`, `49152-49200/udp` (host mode) | Coturn STUN/TURN server |
| `jitsi` | `jitsi-prosody`, `jitsi-jicofo`, `jitsi-jvb`, `jitsi-web` | `10001/udp`, `8443` | Full Jitsi Meet stack |

---

## Environment Variables

Refer to [`env.sample`](env.sample) for all options:

- `COMPOSE_PROFILES`: Comma-separated list of service profiles to activate (`proxy,janus,turn,jitsi`).
- `PUBLIC_IP`: Public IP of the host. If left empty, containers auto-detect the external IP at startup.
- `USE_SSLIP`: Enabled by default (`1`). Automatically routes traffic through `<PUBLIC_IP>.sslip.io` and issues a trusted Let's Encrypt TLS certificate (eliminates browser `ERR_CERT_AUTHORITY_INVALID` warnings). Set `USE_SSLIP=0` to disable.
- `DOMAIN`: Optional custom domain name (e.g., `video.example.com`) for Let's Encrypt TLS.
- `JANUS_ROOM_CREATE_KEY`: Secret used by Eventyay backend to create/manage Janus rooms.
- `COTURN_AUTH_SECRET`: Static shared secret for TURN credential generation.
- `JWT_APP_ID` & `JWT_APP_SECRET`: App ID and secret for Jitsi JWT authentication tokens.
- `JICOFO_AUTH_PASSWORD`: Internal authentication password for Jicofo focus component.
- `JVB_AUTH_PASSWORD`: Internal authentication password for Jitsi Videobridge (JVB).

---

## TLS & Browser Certificate Handling

By default, **automatic wildcard DNS is enabled (`USE_SSLIP=1`)**:
- Caddy automatically derives `<PUBLIC_IP>.sslip.io` and requests a free, trusted public certificate from Let's Encrypt.
- Browsers will trust the connection with a secure padlock and **zero `ERR_CERT_AUTHORITY_INVALID` warnings**.

Options:
- **Default (Zero Config)**: Keep `USE_SSLIP=1` (or leave unset). Access services at `https://<your-ip>.sslip.io`.
- **Custom Domain**: Set `DOMAIN=video.example.com` in `.env` (pointing to your server IP). Caddy will request a Let's Encrypt certificate for your custom domain.
- **Raw IP only**: Set `USE_SSLIP=0` in `.env`. Caddy falls back to generating a self-signed certificate (`tls internal`) for the raw IP.

# TURN Server Deployment (coturn)

For Eventyay Video features (WebRTC), a STUN/TURN server is required to relay traffic when direct peer-to-peer connections fail. We recommend using [coturn](https://github.com/coturn/coturn).

## Deployment Options

### 1. Docker Deployment (Recommended)

You can deploy `coturn` easily using Docker on any VPS (DigitalOcean Droplet, EC2, Compute Engine).

```bash
docker run -d --network=host --name=coturn \
    -v $(pwd)/turnserver.conf:/etc/coturn/turnserver.conf \
    coturn/coturn
```

#### Minimal Configuration on Command Line

```bash
docker run -d -p 3478:3478 -p 3478:3478/udp \
    -p 5349:5349 -p 5349:5349/udp \
    -p 49152-65535:49152-65535/udp \
    coturn/coturn \
    -n --log-file=stdout \
    --min-port=49152 --max-port=65535 \
    --realm=your-domain.com \
    --user=user:password \
    --lt-cred-mech
```

### 2. Configuration (`turnserver.conf`)

For production, mount a configuration file:

```ini
# TURN Server Public IP
external-ip=<YOUR_PUBLIC_IP>

# Listener Port
listening-port=3478
tls-listening-port=5349

# Realm (Domain)
realm=turn.example.com

# Authentication
lt-cred-mech
user=eventyay:secure_password

# SSL/TLS (Optional but Recommended)
# cert=/etc/letsencrypt/live/turn.example.com/fullchain.pem
# pkey=/etc/letsencrypt/live/turn.example.com/privkey.pem
```

## Integration with Eventyay

Once deployed, configure Eventyay to use this TURN server via environment variables or settings:

- `TURN_URL`: `turn:turn.example.com:3478`
- `TURN_USER`: `eventyay`
- `TURN_PASSWORD`: `secure_password`

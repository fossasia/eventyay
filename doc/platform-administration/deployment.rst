Deployment and reverse proxy
============================

Production deployments need HTTPS, a supported database, Redis, and a reverse
proxy. The existing NGINX and URL-path configuration is the detailed reverse
proxy reference.

If voucher rate limiting is used behind reverse proxies, set
``EVY_VOUCHER_RATE_LIMIT_TRUSTED_PROXIES`` in the deployment environment to the
exact proxy IP addresses or CIDR ranges. Include each proxy in the forwarding
chain and configure the ingress to sanitize ``X-Forwarded-For``. Requests from
untrusted peers use their direct connection address; forwarded headers from
those peers are ignored.

.. toctree::
   :maxdepth: 1

   ../deployment/nginx_and_url_path_config

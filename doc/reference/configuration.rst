.. _`config`:

Configuration
=============

Eventyay uses Pydantic Settings to manage configuration. You can configure the application using environment variables, a ``.env`` file, TOML configuration files, or Docker secrets.

Configuration Sources
---------------------

Eventyay reads configuration from the following sources, in order of priority (from highest to lowest):

1. **Secret files** in the ``.secrets/`` directory or Docker Secrets.
2. **Environment variables** (prefixed with ``EVY_``).
3. **``.env`` file** in the current working directory.
4. **Local TOML configuration file** (``eventyay.local.toml``).
5. **Environment-specific TOML configuration file** (``eventyay.{active_environment}.toml``).

The active environment is determined by the ``EVY_RUNNING_ENVIRONMENT`` environment variable (defaults to ``development``). Possible values are ``production``, ``development``, and ``testing``.

TOML Example
------------

If you prefer to use a TOML configuration file (e.g., ``eventyay.production.toml``), it should look like this:

.. code-block:: toml

    debug = false
    secret_key = "your-very-secret-key"
    postgres_db = "eventyay-db"
    redis_url = "redis://localhost/0"
    site_url = "https://eventyay.example.com"

Environment Variables Example
-----------------------------

If you prefer to use environment variables (or a ``.env`` file), you must prefix every setting with ``EVY_``.

.. code-block:: bash

    EVY_DEBUG=false
    EVY_SECRET_KEY="your-very-secret-key"
    EVY_POSTGRES_DB="eventyay-db"
    EVY_REDIS_URL="redis://localhost/0"
    EVY_SITE_URL="https://eventyay.example.com"

Available Settings
------------------

Below is a list of the most common configuration settings. For TOML, use the exact name. For environment variables, prefix the name with ``EVY_``.

General Settings
~~~~~~~~~~~~~~~~

``debug``
    Whether or not to run in debug mode. Default is ``false``.
    **WARNING:** Never set this to ``true`` in production!

``secret_key``
    The secret to be used by Django for cryptographic signing. You must provide a secure, random string in production.

``instance_name``
    The name of this installation. Default: ``eventyay``.

``site_url``
    The primary URL for the installation (e.g., ``https://eventyay.com``).

``short_url``
    A shorter URL domain used for short links.

``allowed_hosts``
    A list of host/domain names that this Django site can serve.

Database Settings
~~~~~~~~~~~~~~~~~

``postgres_db``
    The PostgreSQL database name. Default: ``eventyay-db``.

``postgres_user``, ``postgres_password``, ``postgres_host``, ``postgres_port``
    Connection details for PostgreSQL. If left empty, "peer" authentication will be attempted.

Redis Settings
~~~~~~~~~~~~~~

``redis_url``
    The URL for the Redis server used for caching, sessions, and Celery broker/backend. 
    Default: ``redis://localhost/0``.

Email Settings
~~~~~~~~~~~~~~

``email_backend``
    The Django email backend class. Default is ``django.core.mail.backends.console.EmailBackend`` for local development. Set to ``django.core.mail.backends.smtp.EmailBackend`` for production.

``email_host``, ``email_port``
    The SMTP Host and port to connect to. Default: ``localhost`` and ``587``.

``email_host_user``, ``email_host_password``
    The SMTP authentication credentials.

``email_use_tls``
    Whether to use TLS for SMTP connections. Default: ``true``.

``default_from_email``
    The default email address used in the ``From`` header for outgoing emails.

Plugins & Modules
~~~~~~~~~~~~~~~~~

``plugins_default``
    A list of plugins that are enabled by default for all new events.

``plugins_exclude``
    A list of plugins that are completely disabled for the installation.

``core_modules``
    Core application modules required for the Talk functionality.

Metrics & Sentry
~~~~~~~~~~~~~~~~

``sentry_dsn``
    The Data Source Name (DSN) for Sentry error tracking. Empty by default.

``metrics_enabled``
    Whether to expose prometheus metrics. Default: ``false``.

``metrics_user``, ``metrics_passphrase``
    Basic authentication credentials required to scrape the metrics endpoint.

Upload Limits
~~~~~~~~~~~~~

You can configure upload limits (in Megabytes) for different types of files:

* ``upload_size_csv`` (Default: 10)
* ``upload_size_image`` (Default: 10)
* ``upload_size_pdf`` (Default: 10)
* ``upload_size_xlsx`` (Default: 2)
* ``upload_size_attachment`` (Default: 10)
* ``upload_size_mail`` (Default: 4)
* ``upload_size_question`` (Default: 20)
* ``upload_size_other`` (Default: 10)

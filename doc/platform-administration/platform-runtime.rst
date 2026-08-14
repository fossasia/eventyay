Eventyay platform runtime
=========================

This page describes the stable runtime contract of the unified Eventyay
platform. It is intended for platform operators who need to understand which
processes make up an installation, where configuration comes from, what data
must be persisted, and how to perform routine checks.

The platform is one Django application. Ticketing, proposals and schedules,
online-event features, check-in, plugins, and the public event pages share the
same application settings and database. They are not installed as separate
Tickets, Talk, or Video services.

Runtime components
------------------

An operational installation consists of the following components:

.. list-table::
   :header-rows: 1
   :widths: 22 42 36

   * - Component
     - Responsibility
     - Repository evidence
   * - Web application
     - Serves the Django application, public event pages, organiser pages, and
       administration endpoints.
     - ``eventyay/config/asgi.py`` and ``eventyay/config/wsgi.py`` select the
       production environment and Django settings module.
   * - Celery worker
     - Processes asynchronous jobs such as work scheduled by the application.
     - The repository starts it with ``celery -A eventyay worker -l info``.
   * - Celery beat
     - Publishes scheduled jobs using the Django database scheduler.
     - The repository starts it with ``celery -A eventyay beat -l info
       --scheduler django_celery_beat.schedulers:DatabaseScheduler``.
   * - PostgreSQL
     - Stores Eventyay's application data and the Celery beat schedule.
     - Production configuration defines PostgreSQL settings in
       ``eventyay.production.toml``.
   * - Redis
     - Provides the configured cache and Redis-backed services. Celery derives
       its broker and result databases from the configured Redis URL.
     - ``settings.py`` sets ``HAS_REDIS``, the cache locations, and the Celery
       broker/result URLs.
   * - Reverse proxy
     - Terminates HTTPS and forwards requests to the web application.
     - See the :doc:`NGINX and URL-path guide </platform-administration/deployment>`.

The exact process supervisor and reverse-proxy layout are deployment choices;
the application contract is the set of processes and dependencies above.

Configuration model
-------------------

The active environment is selected with ``EVY_RUNNING_ENVIRONMENT``. Supported
values in the repository are ``development``, ``testing``, and ``production``.
The web and ASGI/WSGI entry points use ``production`` for deployed processes;
the development tools use ``development`` unless overridden.

The settings loader discovers these TOML files:

* ``eventyay.<environment>.toml`` for the active environment
* ``eventyay.local.toml`` for local overrides

Configuration sources are applied in this order, from highest priority to
lowest priority:

#. Secret files in ``.secrets/``. Each file name uses the ``EVY_`` prefix and
   contains the value for one setting. Docker Secrets are supported by the
   same settings source.
#. Environment variables with the ``EVY_`` prefix, for example
   ``EVY_SITE_URL`` or ``EVY_POSTGRES_HOST``.
#. A ``.env`` file in the current working directory.
#. ``eventyay.local.toml``.
#. ``eventyay.<environment>.toml``.

Keep passwords, API keys, and the production secret key in secret files or the
deployment secret store. Do not commit ``.env`` files containing production
credentials or create a production deployment from the development defaults.

The complete setting list is maintained in the
:doc:`configuration reference </reference/configuration>`. The repository's
``.env.dev`` is an example for local Docker development and is not a production
configuration template.

Database, Redis, and background jobs
-------------------------------------

The configured database is exposed to Django through ``DATABASES``. The
production example uses PostgreSQL settings named ``postgres_db``,
``postgres_user``, ``postgres_password``, ``postgres_host``, and
``postgres_port``. The password is intentionally not stored in the example
TOML file.

``redis_url`` is the base Redis URL. Eventyay uses the base URL for Redis-backed
application services and derives separate Redis database numbers for the
Celery broker and result backend. Keep Redis reachable from the web, worker,
and beat processes using the same configuration source.

``celery_always_eager`` controls whether tasks execute immediately in the
calling process. It is enabled in the testing configuration and disabled in
the production configuration. A production installation therefore needs a
running worker; enabling eager execution is not a replacement for the worker
process in production.

Run database migrations before starting an upgraded application version::

   cd app/
   python manage.py migrate

The :doc:`management command reference </reference/management-commands>`
contains the commands available to operators, including migration, rebuild,
periodic-task, and diagnostic commands.

Persistent data and generated files
-----------------------------------

The default data root is ``app/data``. The settings module derives these
locations from it:

* ``data/logs`` for logs
* ``data/media`` for uploaded and user-managed files
* ``data/profiles`` for profile-related data
* ``data/compiled-frontend`` for compiled frontend output
* ``data/htmlexport`` for HTML export output

The application also uses ``STATIC_ROOT`` for collected static files. In the
repository configuration this is ``app/eventyay/static.dist``. Static files
are generated by the application's build commands and should be served by
the web/reverse-proxy arrangement appropriate to the deployment.

Back up the database and the data directories that contain media, profiles,
logs required for operations, and generated exports. A database-only backup
does not restore uploaded media; a filesystem-only backup does not restore
orders, events, users, or configuration stored in the database.

Email delivery
--------------

Email settings are part of the same ``EVY_`` configuration model. The relevant
settings are:

* ``EVY_EMAIL_BACKEND``
* ``EVY_EMAIL_HOST`` and ``EVY_EMAIL_PORT``
* ``EVY_EMAIL_HOST_USER`` and ``EVY_EMAIL_HOST_PASSWORD``
* ``EVY_EMAIL_USE_TLS`` and ``EVY_EMAIL_USE_SSL``
* ``EVY_DEFAULT_FROM_EMAIL``

The development configuration writes email to a local backend so messages can
be inspected during development. The production example selects Django's SMTP
backend. Configure and test the sender identity with the selected mail
provider before exposing an event publicly.

Do not enable both TLS and SSL. The application's configuration checks reject
that combination because only one transport mode can be active at a time.

Startup and upgrade sequence
----------------------------

For a deployment using separate managed processes, use this order when
installing or upgrading:

#. Make the new application code and its dependencies available to the web,
   worker, and beat processes.
#. Provide the same environment selection and configuration sources to all
   processes.
#. Ensure PostgreSQL and Redis are reachable.
#. Run ``python manage.py migrate`` from ``app/``.
#. Run the static/frontend rebuild required by the deployment. The repository
   provides ``python manage.py rebuild`` and the ``app/Makefile`` targets for
   static assets.
#. Restart or roll the web, worker, and beat processes together so they run
   the same application version.
#. Check the application health endpoint and review worker/beat logs.

Do not run migrations concurrently from multiple release processes. Take a
database backup before migrations that change populated tables.

Health and operational checks
-----------------------------

The application exposes ``/healthcheck/``. Its implementation checks:

* that a database query succeeds;
* that Redis is reachable when Redis is enabled;
* that the configured Django cache can write and read a value.

A successful response is empty with HTTP 200. A failed Redis or cache check
returns HTTP 503. Place the endpoint behind the deployment's normal host and
HTTPS routing, and use it for load-balancer or process-supervisor checks.

When investigating a failure, check the dependency corresponding to the
failed layer first:

.. list-table::
   :header-rows: 1
   :widths: 28 42 30

   * - Symptom
     - First checks
     - Relevant reference
   * - Database errors or health-check failure
     - PostgreSQL availability, credentials, host/port, and pending
       migrations.
     - :doc:`configuration reference </reference/configuration>`
   * - Redis or cache health-check failure
     - ``redis_url``, network reachability, and Redis logs.
     - This page's Redis section
   * - Jobs remain pending
     - Worker process, broker URL, worker logs, and whether beat is running for
       scheduled jobs.
     - :doc:`management commands </reference/management-commands>`
   * - Emails are not delivered
     - Email backend, SMTP host/port, TLS/SSL mode, credentials, and sender
       identity.
     - :doc:`email implementation reference </developer-guide/backend>`
   * - Static files are missing after deployment
     - Rebuild/collect static output and reverse-proxy paths.
     - :doc:`deployment guide </platform-administration/deployment>`

Security baseline
-----------------

Production deployments should:

* use HTTPS at the public reverse proxy;
* set a unique production ``EVY_SECRET_KEY`` through a secret source;
* restrict ``EVY_ALLOWED_HOSTS`` to the installation's hostnames;
* keep database, Redis, SMTP, and secret-file credentials out of source
  control;
* avoid exposing PostgreSQL and Redis directly to the public network; and
* run web, worker, and beat processes with the same release and configuration.

These are operational requirements implied by the application's settings and
deployment model. Network topology, service supervision, backup retention,
and alerting remain responsibilities of the platform operator.

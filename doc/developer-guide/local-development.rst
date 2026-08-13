Local development setup
=======================

Use one development environment for the unified Eventyay codebase. The repository's Python baseline is 3.12 and application code lives under ``app/``.

Quick start with Docker
-----------------------

Docker is the recommended way to start quickly.

Requirements:

* Docker
* Docker Compose plugin
* Git

Steps:

.. code-block:: bash

   git clone https://github.com/fossasia/eventyay.git
   cd eventyay
   git switch dev

   cp deployment/env.dev.sample .env.dev

   docker compose up -d --build

Create an admin user:

.. code-block:: bash

   docker exec -ti eventyay-next-web python manage.py create_admin_user

Open the local site:

.. code-block:: text

   http://localhost:8000

View logs:

.. code-block:: bash

   docker compose logs -f

Stop the development stack:

.. code-block:: bash

   docker compose down

The directory ``app/eventyay`` is mounted into the Docker container, so live editing of backend code is supported.

Python based local development
------------------------------

Use this setup when you want to run services directly on your machine.

Requirements:

* Python 3.12
* `uv <https://docs.astral.sh/uv/getting-started/installation/>`_
* PostgreSQL
* Redis
* Node.js and npm
* Debian or Ubuntu packages listed in ``deb-packages.txt`` or equivalent packages for your distribution

Clone the repository:

.. code-block:: bash

   git clone https://github.com/fossasia/eventyay.git
   cd eventyay
   git switch dev

Install external dependencies on Debian or Ubuntu:

.. code-block:: bash

   xargs -a deb-packages.txt sudo apt install

For Nushell:

.. code-block:: nu

   open deb-packages.txt | lines | sudo apt install ...$in

If you are using another Linux distribution, install the corresponding packages from ``deb-packages.txt``.

Install `uv <https://docs.astral.sh/uv/getting-started/installation/>`_.

Install and run Redis according to your distribution.

Create a PostgreSQL database. The default local database name is:

.. code-block:: text

   eventyay-db

On Linux, the simplest local development setup is PostgreSQL peer mode. Create a PostgreSQL user with the same name as your Linux user:

.. code-block:: bash

   sudo -u postgres createuser -s "$USER"

Then create a database owned by your user:

.. code-block:: bash

   createdb eventyay-db

You can then access the database without specifying a password, host, or port:

.. code-block:: bash

   psql eventyay-db

If you cannot use PostgreSQL peer mode, create ``app/eventyay.local.toml`` with database connection values:

.. code-block:: toml

   postgres_user = "your_db_user"
   postgres_password = "your_db_password"
   postgres_host = "localhost"
   postgres_port = 5432

Enter the app directory:

.. code-block:: bash

   cd app

Install Python dependencies:

.. code-block:: bash

   uv sync --all-extras --all-groups

Activate the virtual environment:

.. code-block:: bash

   . .venv/bin/activate

Run migrations:

.. code-block:: bash

   python manage.py migrate

Create an admin user:

.. code-block:: bash

   python manage.py create_admin_user

Build frontend and static assets:

.. code-block:: bash

   make npminstall
   python manage.py collectstatic --noinput
   python manage.py compress --force

Run the development server:

.. code-block:: bash

   python manage.py runserver

Open:

.. code-block:: text

   http://localhost:8000

Run Celery locally when working on background tasks:

.. code-block:: bash

   celery -A eventyay worker -l info

Run the test suite:

.. code-block:: bash

   pytest tests/

Mobile testing note
~~~~~~~~~~~~~~~~~~~

If you want to test the site from an Android emulator, use:

.. code-block:: text

   http://10.0.2.2:8000/

This is Android's alias for the host machine's localhost.

Permission note
~~~~~~~~~~~~~~~

If you get permission errors for ``eventyay/static/CACHE``, make sure that the directory and all files below it are owned by your user.

For backend structure, frontend details, testing conventions, translations, and plugin development, continue with the pages in this Developer guide.

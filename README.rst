eventyay-tickets (ENext)
========================

.. image:: https://img.shields.io/github/stars/fossasia/eventyay?style=social
   :target: https://github.com/fossasia/eventyay

.. image:: https://img.shields.io/github/forks/fossasia/eventyay
   :target: https://github.com/fossasia/eventyay/network

.. image:: https://img.shields.io/github/issues/fossasia/eventyay
   :target: https://github.com/fossasia/eventyay/issues

.. image:: https://img.shields.io/github/license/fossasia/eventyay
   :target: https://github.com/fossasia/eventyay/blob/dev/LICENSE


Project status & release cycle
------------------------------

Welcome to the **Eventyay** project! The ticketing component of the system provides options for **ticket sales and event-related items** such as T-shirts. Eventyay has been in development since **2014**. Its ticketing component is based on a fork of **Pretix**.

ENext is the new and updated version of Eventyay with a unified codebase for the Tickets, Talk, and Videos components.


External Dependencies
---------------------

The *deb-packages.txt* file lists Debian packages we need to install.
If you are using Debian / Ubuntu, you can install them quickly with this command:

For traditional shell:

.. code-block:: bash

  $ xargs -a deb-packages.txt sudo apt install

For Nushell:

.. code-block:: nu

  > open deb-packages.txt | lines | sudo apt install ...$in

If you are using other Linux distributions, please install the corresponding packages listed in *deb-packages.txt*.

Other than that, please install `uv`_, the Python package manager.


Getting Started
---------------

1. **Clone the repository**:

.. code-block:: bash

  git clone https://github.com/fossasia/eventyay.git

2. **Enter the project directory and app directory**:

.. code-block:: bash

  cd eventyay/app

3. **Switch to the `dev` branch**:

.. code-block:: bash

  git switch dev

4. **Install Python packages**

Use ``uv`` to create a virtual environment and install Python packages at the same time.  
**Make sure you are in the app directory.**

.. code-block:: sh

  uv sync --all-extras --all-groups

5. **Create a PostgreSQL database**

The default database name required by the project is ``eventyay-db``. If you are using Linux, the simplest way to work with the database is to use its *peer* mode (no need to remember a password).

Create a PostgreSQL user with the same name as your Linux user:

.. code-block:: sh

  sudo -u postgres createuser -s $USER

(``-s`` means *superuser*)

Then create a database owned by your user:

.. code-block:: sh

  createdb eventyay-db

From now on, you can work with the database without specifying password, host, or port.

.. code-block:: sh

  psql eventyay-db

If you cannot use PostgreSQL *peer* mode, create a *eventyay.local.toml* file with the following values:

.. code-block:: toml

  postgres_user = "your_db_user"
  postgres_password = "your_db_password"
  postgres_host = "localhost"
  postgres_port = 5432

6. **Install and run Redis**

Make sure Redis is installed and running before starting the development server.

For Debian / Ubuntu:

.. code-block:: bash

  sudo apt install redis-server
  sudo systemctl start redis
  sudo systemctl enable redis

You can verify Redis is running with:

.. code-block:: bash

  redis-cli ping

It should return:

::

  PONG

7. **Activate the virtual environment**

After running ``uv sync``, activate the virtual environment:

.. code-block:: sh

  . .venv/bin/activate

8. **Initialize the database**:

.. code-block:: bash

  python manage.py migrate

9. **Create an admin user account** (for accessing the admin panel):

.. code-block:: bash

  python manage.py create_admin_user

10. **Run the development server**:

.. code-block:: bash

  python manage.py runserver

Mobile testing note: If you want to test the site from an **Android emulator**, use  
``http://10.0.2.2:8000/`` (Android's alias for the host machine's localhost).

Notes: If you get permission errors for ``eventyay/static/CACHE``, make sure that the directory and all files within it are owned by your user.


Docker based development
------------------------

We assume your current working directory is the checkout of this repository.

1. **Create .env.dev**

   .. code-block:: bash

      cp deployment/env.sample .env.dev

2. **Edit .env.dev**

   Change <SERVER_NAME> and update `EVY_RUNNING_ENVIRONMENT=production`
   to `EVY_RUNNING_ENVIRONMENT=development`.

3. **Remove old volumes (if necessary)**

   This is only necessary the first time, or if you encounter unexpected behaviour.  
   This removes the database volume and triggers a complete reinitialization.  
   After that, you will need to run migrations and create a superuser again.

   .. code-block:: bash

      docker volume rm eventyay_postgres_data_dev eventyay_static_volume

4. **Build and run the images**

   .. code-block:: bash

      docker compose up -d --build

5. **Run database migrations**

   .. code-block:: bash

      docker exec -ti eventyay-next-web python manage.py makemigrations
      docker exec -ti eventyay-next-web python manage.py migrate

6. **Create a superuser account**

   .. code-block:: bash

      docker exec -ti eventyay-next-web python manage.py createsuperuser

7. **Visit the site**

   Open ``http://localhost:8000`` in your browser.

8. **Troubleshooting: CSS not loading / MIME type errors**

   If pages load without CSS, it usually means a static asset returned an HTML response (e.g., a 404 page).

   Rebuild static assets:

   .. code-block:: bash

      docker exec -ti eventyay-next-web python manage.py collectstatic --noinput
      docker exec -ti eventyay-next-web python manage.py compress --force
      docker restart eventyay-next-web

   After this, hard-refresh the browser (Ctrl + Shift + R).

9. **Checking logs**

   .. code-block:: bash

      docker compose logs -f

10. **Shut down**

   .. code-block:: bash

      docker compose down

The directory ``app/eventyay`` is mounted into Docker, so live editing is supported.


Configuration
-------------

Our configuration is based on TOML files. First, check the ``BaseSettings`` class in *app/eventyay/config/next_settings.py* for possible keys and default values.

The configuration is divided into three environments:

* ``development`` — default values in *eventyay.development.toml*
* ``production`` — default values in *eventyay.production.toml*
* ``testing`` — default values in *eventyay.testing.toml*

Values in these files override those in ``BaseSettings``.

The running environment is selected via the ``EVY_RUNNING_ENVIRONMENT`` environment variable.

Example:

.. code-block:: bash

  EVY_RUNNING_ENVIRONMENT=production ./manage.py command
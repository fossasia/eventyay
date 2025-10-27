.. highlight:: none

Installing a development version
================================

If you want to use a feature of Eventyay that is not yet contained in the last monthly release, you can also
install a development version with Eventyay.

.. warning:: When in production, we strongly recommend only installing released versions. Development versions might
             be broken, incompatible to plugins, or in rare cases incompatible to upgrade later on.


Manual installation
-------------------

You can use ``pip`` to update Eventyay directly to the development branch. Then, upgrade as usual::

    $ source /var/eventyay/venv/bin/activate
    (venv)$ pip3 install -U "git+https://github.com/fossasia/eventyay.git#egg=Eventyay&subdirectory=src"
    (venv)$ python -m Eventyay migrate
    (venv)$ python -m Eventyay rebuild
    (venv)$ python -m Eventyay updatestyles
    # systemctl restart Eventyay-web Eventyay-worker

Docker installation
-------------------

To use the latest development version with Docker, first pull it from Docker Hub::

    $ docker pull fossasia/eventyay-tickets:latest


Then change your ``/etc/systemd/system/Eventyay.service`` file to use the ``:latest`` tag instead of ``:stable`` as well
and upgrade as usual::

    $ systemctl restart Eventyay.service
    $ docker exec -it Eventyay.service Eventyay upgrade

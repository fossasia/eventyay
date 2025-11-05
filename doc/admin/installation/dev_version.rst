.. highlight:: none

Installing a development version
================================

If you want to use a feature of eventyay that is not yet contained in the last monthly release, you can also
install a development version with eventyay.

.. warning:: When in production, we strongly recommend only installing released versions. Development versions might
             be broken, incompatible to plugins, or in rare cases incompatible to upgrade later on.


Manual installation
-------------------

You can use ``pip`` to update eventyay directly to the development branch. Then, upgrade as usual::

    $ source /var/eventyay/venv/bin/activate
    (venv)$ pip3 install -U "git+https://github.com/fossasia/eventyay.git#egg=eventyay&subdirectory=src"
    (venv)$ python -m eventyay migrate
    (venv)$ python -m eventyay rebuild
    (venv)$ python -m eventyay updatestyles
    # systemctl restart eventyay-web eventyay-worker

Docker installation
-------------------

To use the latest development version with Docker, first pull it from Docker Hub::

    $ docker pull fossasia/eventyay-tickets:latest


Then change your ``/etc/systemd/system/eventyay.service`` file to use the ``:latest`` tag instead of ``:stable`` as well
and upgrade as usual::

    $ systemctl restart eventyay.service
    $ docker exec -it eventyay.service eventyay upgrade

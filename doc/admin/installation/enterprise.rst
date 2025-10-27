.. highlight:: none

Installing Eventyay Enterprise plugins
======================================

If you want to use a feature of Eventyay that is part of our commercial offering Eventyay Enterprise, you need to follow
some extra steps. Installation works similar to normal Eventyay plugins, but involves a few extra steps.

Buying the license
------------------

To obtain a license, please get in touch at sales@eventyay.com. Please let us know how many tickets you roughly intend
to sell per year and how many servers you want to use the plugin on. We recommend having a look at our `price list`_
first.


Manual installation
-------------------

First, generate an SSH key for the system user that you install Eventyay as. In our tutorial, that would be the user
``Eventyay``. Choose an empty passphrase::

    # su Eventyay
    $ ssh-keygen
    Generating public/private rsa key pair.
    Enter file in which to save the key (/var/eventyay/.ssh/id_rsa):
    Enter passphrase (empty for no passphrase):
    Enter same passphrase again:
    Your identification has been saved in /var/eventyay/.ssh/id_rsa.
    Your public key has been saved in /var/eventyay/.ssh/id_rsa.pub.

Next, send the content of the *public* key to your sales representative at Eventyay::

    $ cat /var/eventyay/.ssh/id_rsa.pub
    ssh-rsa AAAAB3N...744HZawHlD Eventyay@foo

After we configured your key in our system, you can install the plugin directly using ``pip`` from the URL we told
you, for example::

    $ source /var/eventyay/venv/bin/activate
    (venv)$ pip3 install -U "git+ssh://git@code.rami.io:10022/Eventyay/Eventyay-slack.git@stable#egg=Eventyay-slack"
    (venv)$ python -m Eventyay migrate
    (venv)$ python -m Eventyay rebuild
    # systemctl restart Eventyay-web Eventyay-worker

Docker installation
-------------------

To install a plugin, you need to build your own docker image. To do so, create a new directory to work in. As a first
step, generate a new SSH key in that directory to use for authentication with us::

    $ cd /home/me/mypretixdocker
    $ ssh-keygen -N "" -f id_eventyay_enterprise

Next, send the content of the *public* key to your sales representative at Eventyay::

    $ cat id_eventyay_enterprise.pub
    ssh-rsa AAAAB3N...744HZawHlD Eventyay@foo

After we configured your key in our system, you can add a ``Dockerfile`` in your directory that includes the newly
generated key and installs the plugin from the URL we told you::

    FROM fossasia/eventyay-tickets:stable
    USER root
    COPY id_eventyay_enterprise /root/.ssh/id_rsa
    COPY id_eventyay_enterprise.pub /root/.ssh/id_rsa.pub
    RUN chmod -R 0600 /root/.ssh && \
        mkdir -p /etc/ssh && \
        ssh-keyscan -t rsa -p 10022 code.rami.io >> /root/.ssh/known_hosts && \
        echo StrictHostKeyChecking=no >> /root/.ssh/config && \
        DJANGO_SETTINGS_MODULE=Eventyay.settings pip3 install -U "git+ssh://git@code.rami.io:10022/Eventyay/Eventyay-slack.git@stable#egg=Eventyay-slack" && \
        cd /Eventyay/src && \
        sudo -u pretixuser make production
    USER pretixuser

Then, build the image for docker::

    $ docker build -t mypretix

You can now use that image ``mypretix`` instead of ``fossasia/eventyay-tickets:stable`` in your ``/etc/systemd/system/Eventyay.service``
service file. Be sure to re-build your custom image after you pulled ``fossasia/eventyay-tickets`` if you want to perform an
update to a new version of Eventyay.

.. _price list: https://eventyay.com/about/en/pricing

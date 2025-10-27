.. highlight:: python
   :linenothreshold: 5

Writing an e-mail placeholder plugin
====================================

An email placeholder is a dynamic value that Eventyay users can use in their email templates.

Please read :ref:`Creating a plugin <pluginsetup>` first, if you haven't already.

Placeholder registration
------------------------

The placeholder API does not make a lot of usage from signals, however, it
does use a signal to get a list of all available email placeholders. Your plugin
should listen for this signal and return an instance of a subclass of ``eventyay.base.email.BaseMailTextPlaceholder``:

.. code-block:: python

    from django.dispatch import receiver

    from eventyay.base.signals import register_mail_placeholders


    @receiver(register_mail_placeholders, dispatch_uid="placeholder_custom")
    def register_mail_renderers(sender, **kwargs):
        from .email import MyPlaceholderClass
        return MyPlaceholder()


Context mechanism
-----------------

Emails are sent in different "contexts" within Eventyay. For example, many emails are sent in the
the context of an order, but some are not, such as the notification of a waiting list voucher.

Not all placeholders make sense in every email, and placeholders usually depend some parameters
themselves, such as the ``Order`` object. Therefore, placeholders are expected to explicitly declare
what values they depend on and they will only be available in an email if all those dependencies are
met. Currently, placeholders can depend on the following context parameters:

* ``event``
* ``order``
* ``position``
* ``waiting_list_entry``
* ``invoice_address``
* ``payment``

There are a few more that are only to be used internally but not by plugins.

The placeholder class
---------------------

.. class:: eventyay.base.email.BaseMailTextPlaceholder

   .. py:attribute:: identifier

      A short and unique identifier for this placeholder.

      This is an abstract attribute, you **must** override this!

   .. py:attribute:: required_context

      A list of context parameters that this placeholder requires. For example, ``['order']`` or ``['event', 'position']``.

      This is an abstract attribute, you **must** override this!

   .. py:method:: render(context)

      Render the placeholder value.

      :param context: A dictionary containing the context parameters declared in ``required_context``.
      :return: The rendered placeholder value as a string.

      This is an abstract method, you **must** implement this!

   .. py:method:: render_sample(event)

      Render a sample placeholder value for documentation purposes.

      :param event: The event to render a sample for.
      :return: A sample value as a string.

      This is an abstract method, you **must** implement this!

Helper class for simple placeholders
------------------------------------

Eventyay ships with a helper class that makes it easy to provide placeholders based on simple
functions:

.. code-block:: python

     placeholder = SimpleFunctionalMailTextPlaceholder(
         'code', ['order'], lambda order: order.code, sample='F8VVL'
     )

